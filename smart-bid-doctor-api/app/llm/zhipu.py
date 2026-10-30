"""智谱 GLM Provider（OpenAI 兼容接口，01·D1）——编排骨架已实装，HTTP 调用点 TODO。

编排链（chat）：熔断检查 → token 预算检查 → 重试调用（429/5xx 指数退避 ≤3 次）
→ 用量预算累计 → llm_calls 记账（成功/失败均记，独立事务，失败不阻断主流程）。
模型名/base_url 全部来自配置（02 §7），换供应商（DeepSeek/Qwen）= 改 base_url + 模型名。

Agent 能力 TODO 边界（AGENTS.md 硬性禁区 1）：仅 `_post_chat` / `_post_embed` 两个
HTTP 调用体保持 TODO(M1/A1–A3)——接入时补 httpx POST + Bearer 鉴权即可，重试/熔断/
记账/预算/Prompt 模板读取均已就绪并有 mock 单测（tests/test_llm_provider.py）。
桩状态（NOT_IMPLEMENTED）不进熔断计数、不落 llm_calls（避免污染成本报表）。

熔断器（05 §9.3）：进程内连续失败计数，超阈值熔断窗口期内快速失败（LLM_CIRCUIT_OPEN，
不耗配额）；成功一次即清零。阈值/窗口进 sys_config（llm.circuit_break_threshold /
llm.circuit_break_seconds），worker 启动时经 refresh_breaker() 热载。
"""

import logging
import time
from decimal import Decimal

from app.core.config import Settings, get_settings
from app.core.errors import ERROR_CODES, AppError
from app.llm.base import ChatResult
from app.llm.budget import BudgetExceeded, budget, budget_for

log = logging.getLogger("llm.zhipu")

MAX_RETRY = 3  # 429/5xx 指数退避重试上限（02 §7）
RETRYABLE_STATUS = (429, 500, 502, 503, 504)

# 熔断默认值（sys_config 未配置时的兜底；05 §9.3：连续 5 次失败熔断 5 分钟）
DEFAULT_CIRCUIT_THRESHOLD = 5
DEFAULT_CIRCUIT_SECONDS = 300

# worker 域错误码（errors.py 注册表 status=0；handler 写 tasks.error_code 用常量）
CODE_CIRCUIT_OPEN = "LLM_CIRCUIT_OPEN"


class LLMHTTPError(Exception):
    """Provider HTTP 调用非 2xx（_post_chat/_post_embed 抛出；429/5xx 可重试）。"""

    def __init__(self, status: int, body: str = ""):
        self.status = status
        self.body = body[:500]
        super().__init__(f"LLM HTTP {status}: {self.body}")


class CircuitOpenError(Exception):
    """熔断期快速失败：handler 捕获后写 tasks.error_code=CODE_CIRCUIT_OPEN
    （任务 need_review，未发起真实调用、未计费）。"""


class CircuitBreaker:
    """进程内熔断器（单机部署基线）：连续失败 ≥threshold 即开断 seconds 秒。"""

    def __init__(self, threshold: int = DEFAULT_CIRCUIT_THRESHOLD,
                 seconds: int = DEFAULT_CIRCUIT_SECONDS):
        self.threshold = threshold
        self.seconds = seconds
        self._consecutive = 0
        self._opened_until = 0.0  # time.monotonic() 口径

    def configure(self, *, threshold: int, seconds: int) -> None:
        """sys_config 热载（worker 启动/每轮调用 refresh_breaker）。"""
        if threshold > 0:
            self.threshold = threshold
        if seconds > 0:
            self.seconds = seconds

    def is_open(self) -> bool:
        return time.monotonic() < self._opened_until

    def record_success(self) -> None:
        self._consecutive = 0

    def record_failure(self) -> None:
        self._consecutive += 1
        if self._consecutive >= self.threshold:
            self._opened_until = time.monotonic() + self.seconds
            log.warning("LLM 熔断开启：%s 次连续失败，窗口 %ss", self._consecutive, self.seconds)
            self._consecutive = 0

    def reset(self) -> None:
        """测试专用：清进程内状态（autouse fixture，与限流器同约定）。"""
        self._consecutive = 0
        self._opened_until = 0.0


breaker = CircuitBreaker()

# 内置默认 Prompt（prompt_templates 无 active 版时的兜底；管理端 AI 治理页可上传
# 版本化模板覆盖，切换须先过金标评测锚定 eval_score，05 §9.3）
DEFAULT_SYSTEM_PROMPT = (
    "你是标书合规审查专家。严格按用户给定的 JSON Schema 输出 JSON，"
    "不得输出 JSON 以外的任何文本；依据不足时宁可标注不确定，绝不臆造。"
)


def default_messages(system: str | None, user: str) -> list[dict]:
    """组装 messages：system 缺省用内置默认 Prompt（json_mode 契约在 payload 层）。"""
    msgs: list[dict] = []
    sys_text = system or DEFAULT_SYSTEM_PROMPT
    if sys_text:
        msgs.append({"role": "system", "content": sys_text})
    msgs.append({"role": "user", "content": user})
    return msgs


class ZhipuProvider:
    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self.api_key = s.zhipu_api_key
        self.base_url = s.zhipu_base_url.rstrip("/")
        # tier → 模型（heavy=抽取/判定，light=摘要/兜底，02 §7）
        self.models = {"heavy": s.llm_model_heavy, "light": s.llm_model_light}
        self.embed_model = s.llm_model_embed
        self._retry_delay = self._backoff  # 可注入覆写（单测免真实 sleep）

    # ── 对话调用（编排骨架就绪）───────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        *,
        json_mode: bool = False,
        tier: str = "heavy",
        max_tokens: int = 4096,
        temperature: float = 0.1,
        task_id: int | None = None,
        project_id: int | None = None,
        purpose: str = "extract",
        prompt_template_id: int | None = None,
    ) -> ChatResult:
        model = self.models.get(tier) or self.models["heavy"]
        self._guard_circuit()
        bud = budget_for(purpose)
        budget_key = task_id if task_id is not None else -1  # 无任务上下文（评测等）共享 -1 桶
        budget.check(budget_key, bud)

        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        try:
            resp = self._retrying(payload, self._post_chat)
        except AppError as exc:
            if exc.code == "NOT_IMPLEMENTED":
                raise  # 桩状态：不记账、不进熔断计数（真实接入后该分支自然失效）
            self._on_failure(exc, task_id=task_id, project_id=project_id, purpose=purpose,
                             model=model, prompt_template_id=prompt_template_id)
            raise
        except Exception as exc:
            self._on_failure(exc, task_id=task_id, project_id=project_id, purpose=purpose,
                             model=model, prompt_template_id=prompt_template_id)
            raise

        latency_ms = int((time.monotonic() - start) * 1000)
        content, usage = _parse_chat_response(resp)
        try:
            budget.add(budget_key, usage["prompt_tokens"] + usage["completion_tokens"], bud)
        except BudgetExceeded as exc:
            # 本次调用已成功，预算超限在「下一次」调用前生效（check 拦截）；此处仅记录
            log.warning("任务 %s token 预算越限（本次调用已计入）：%s", task_id, exc)
        breaker.record_success()
        self._record_call(purpose=purpose, model=model, task_id=task_id,
                          project_id=project_id, prompt_template_id=prompt_template_id,
                          prompt_tokens=usage["prompt_tokens"],
                          output_tokens=usage["completion_tokens"], latency_ms=latency_ms)
        return ChatResult(content=content, prompt_tokens=usage["prompt_tokens"],
                          output_tokens=usage["completion_tokens"], latency_ms=latency_ms)

    # ── 向量化调用（02 §5）───────────────────────────────────────────────────

    def embed(self, texts: list[str], *, task_id: int | None = None,
              project_id: int | None = None) -> list[list[float]]:
        """块向量化（embedding-3，dimensions=1024）。向量成本低，不计 token 预算。"""
        if not texts:
            return []
        model = self.embed_model
        self._guard_circuit()
        payload = {"model": model, "input": list(texts), "dimensions": EMBED_DIM}
        start = time.monotonic()
        try:
            resp = self._retrying(payload, self._post_embed)
        except AppError as exc:
            if exc.code == "NOT_IMPLEMENTED":
                raise
            self._on_failure(exc, task_id=task_id, project_id=project_id,
                             purpose="embed", model=model)
            raise
        except Exception as exc:
            self._on_failure(exc, task_id=task_id, project_id=project_id,
                             purpose="embed", model=model)
            raise
        latency_ms = int((time.monotonic() - start) * 1000)
        vectors = _parse_embed_response(resp, expect=len(texts))
        breaker.record_success()
        self._record_call(purpose="embed", model=model, task_id=task_id,
                          project_id=project_id, latency_ms=latency_ms)
        return vectors

    # ── 编排内部件 ───────────────────────────────────────────────────────────

    def _retrying(self, payload: dict, post) -> dict:
        """429/5xx 指数退避 ≤MAX_RETRY 次；其他异常原样传播。"""
        last: Exception | None = None
        for attempt in range(MAX_RETRY + 1):  # 首次 + ≤3 次重试
            try:
                return post(payload)
            except LLMHTTPError as exc:
                if exc.status not in RETRYABLE_STATUS:
                    raise
                last = exc
                if attempt < MAX_RETRY:
                    self._retry_delay(attempt + 1)
        raise last  # pragma: no cover（循环内必已 raise）

    def _guard_circuit(self) -> None:
        if breaker.is_open():
            raise CircuitOpenError(
                "LLM 服务熔断中，稍后自动恢复；本次调用未发起、未计费"
            )

    @staticmethod
    def _backoff(retry_no: int) -> None:
        time.sleep(min(0.5 * (2 ** (retry_no - 1)), 4.0))

    def _on_failure(self, exc: Exception, *, task_id, project_id, purpose, model,
                    prompt_template_id=None) -> None:
        """真实调用失败：进熔断计数 + 失败记账（error 列记原因，成本 0）。"""
        breaker.record_failure()
        self._record_call(purpose=purpose, model=model, task_id=task_id,
                          project_id=project_id, prompt_template_id=prompt_template_id,
                          error=str(exc)[:500])

    def _record_call(self, *, purpose: str, model: str, task_id: int | None,
                     project_id: int | None, prompt_template_id: int | None = None,
                     prompt_tokens: int = 0, output_tokens: int = 0,
                     latency_ms: int | None = None, error: str | None = None) -> None:
        """llm_calls 记账：独立事务，失败仅告警不阻断（审计/留痕同范式）。

        计价快照读 ai_model_config 注册表（05 §9.3，model_code 匹配；未注册行
        成本记 0、model_id 空，管理端 AI 治理页注册计价后自动出数）。
        """
        from app.core.db import SessionLocal
        from app.models import LlmCall
        from app.services import ai_svc

        try:
            with SessionLocal() as s:
                model_id = None
                in_price = out_price = Decimal("0")
                cfg = ai_svc.get_enabled(s, model)
                if cfg is not None:
                    model_id = cfg.id
                    in_price = Decimal(str(cfg.input_price))
                    out_price = Decimal(str(cfg.output_price))
                cost = ((Decimal(prompt_tokens) * in_price + Decimal(output_tokens) * out_price)
                        / Decimal("1000000")).quantize(Decimal("0.0001"))
                s.add(LlmCall(
                    task_id=task_id, project_id=project_id, purpose=purpose, model=model,
                    prompt_tokens=prompt_tokens, output_tokens=output_tokens, cost_cny=cost,
                    latency_ms=latency_ms, error=error, model_id=model_id,
                    prompt_template_id=prompt_template_id,
                ))
                s.commit()
        except Exception:
            log.warning("llm_calls 记账失败（不阻断主流程）", exc_info=True)

    # ── HTTP 调用点（Agent 能力 TODO 边界）──────────────────────────────────

    # TODO(M1/A1) httpx 直连 OpenAI 兼容接口（02 §7）：
    #   with httpx.Client(base_url=self.base_url, timeout=60) as client:
    #       r = client.post("/chat/completions",
    #                       headers={"Authorization": f"Bearer {self.api_key}"},
    #                       json=payload)
    #   非 2xx → raise LLMHTTPError(r.status_code, r.text)；2xx → return r.json()
    #   验收：FJ_ZHIPU_API_KEY 注入后可真实调用返回结构化文本（本方法之外零改动）。
    def _post_chat(self, payload: dict) -> dict:
        raise AppError(
            ERROR_CODES["NOT_IMPLEMENTED"], "NOT_IMPLEMENTED",
            "LLM 调用未接入（Agent 能力 TODO）——补齐 _post_chat 即插即用，见 02-详细设计 §7",
        )

    # TODO(M1/A2) POST {base_url}/embeddings（02 §5）：model=embedding-3，
    #   dimensions=1024；非 2xx → LLMHTTPError；2xx → return r.json()。
    def _post_embed(self, payload: dict) -> dict:
        raise AppError(
            ERROR_CODES["NOT_IMPLEMENTED"], "NOT_IMPLEMENTED",
            "向量化调用未接入（Agent 能力 TODO）——补齐 _post_embed 即插即用，见 02-详细设计 §5",
        )


# ── 响应解析（OpenAI 兼容结构）──────────────────────────────────────────────

EMBED_DIM = 1024  # 与 app.models.base.EMBED_DIM 对齐（pgvector 列宽）


def _parse_chat_response(resp: dict) -> tuple[str, dict]:
    """choices[0].message.content + usage；结构异常按失败处理（坏响应可重试）。"""
    try:
        content = resp["choices"][0]["message"]["content"]
        usage = resp.get("usage") or {}
        return content or "", {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
        }
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMHTTPError(502, f"bad chat response shape: {exc}") from exc


def _parse_embed_response(resp: dict, *, expect: int) -> list[list[float]]:
    try:
        rows = sorted(resp["data"], key=lambda d: d.get("index", 0))
        vectors = [list(map(float, r["embedding"])) for r in rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMHTTPError(502, f"bad embed response shape: {exc}") from exc
    if len(vectors) != expect or any(len(v) != EMBED_DIM for v in vectors):
        raise LLMHTTPError(502, f"embed dim mismatch: got {len(vectors)}x{[len(v) for v in vectors][:1]}")
    return vectors


def refresh_breaker(db) -> None:
    """sys_config 热载熔断阈值（worker 启动时调用；llm.circuit_break_* 未配置用默认）。"""
    from app.services import config_svc

    breaker.configure(
        threshold=config_svc.get_int(db, "llm.circuit_break_threshold", DEFAULT_CIRCUIT_THRESHOLD),
        seconds=config_svc.get_int(db, "llm.circuit_break_seconds", DEFAULT_CIRCUIT_SECONDS),
    )

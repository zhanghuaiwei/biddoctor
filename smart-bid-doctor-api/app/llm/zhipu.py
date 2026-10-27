"""智谱 GLM Provider（OpenAI 兼容接口，01·D1）。

骨架版不实现真实调用——M1 接入抽取/对照时补齐（HTTP 客户端、重试/熔断、
llm_calls 记账、budget 上限）。模型名/base_url 全部来自配置（02 §7），
换供应商（DeepSeek/Qwen）= 改 base_url + 模型名，不改代码。
"""

from app.core.config import Settings, get_settings
from app.core.errors import ERROR_CODES, AppError
from app.llm.base import ChatResult


class ZhipuProvider:
    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self.api_key = s.zhipu_api_key
        self.base_url = s.zhipu_base_url
        # tier → 模型（heavy=抽取/判定，light=摘要/兜底，02 §7）
        self.models = {"heavy": s.llm_model_heavy, "light": s.llm_model_light}

    # TODO(M1/A1–A3) 推荐方案与实现过程（02 §7）：
    # 推荐方案：httpx 直连 OpenAI 兼容 /chat/completions（base_url/api_key/模型名全配置）；
    #   重试：429/5xx 指数退避 ≤3 次；熔断：连续 5 次失败熔断 5 分钟（进程内状态，
    #   单机部署基线）；记账：每次调用落 llm_calls 一行（task/project/purpose/model/
    #   tokens/cost_cny/latency），token 单价表进配置，成本 Decimal 计价。
    # 实现过程：
    #   1. chat() 组装 messages；json_mode=True 时带 response_format={"type":"json_object"}；
    #   2. 接入 llm/budget.py 任务级 token 上限（CHECKLIST/COMPARE_BUDGET_TOKENS），
    #      累计超限抛专用错误码（ERROR_CODES 登记 + AST 守卫测试同步）；
    #   3. 熔断器（时间窗计数）挂在 chat 入口，熔断期直接快速失败不耗配额；
    #   4. 成功/失败均写 llm_calls（error 列记失败原因），metrics/daily_report 已按
    #      llm_calls 汇总，接入即出成本报表（A3）。
    # 验收：重试/熔断有 mock 单测；配置注入后可真实调用并返回结构化文本。
    def chat(self, messages, *, json_mode=False, tier="heavy", max_tokens=4096,
             temperature=0.1) -> ChatResult:
        raise AppError(
            ERROR_CODES["NOT_IMPLEMENTED"], "NOT_IMPLEMENTED",
            "LLM 调用未接入（骨架版）——M1 实现见 02-详细设计 §7",
        )

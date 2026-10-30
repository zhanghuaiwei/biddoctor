"""LLM Provider 编排骨架单测（02 §7 / 05 §9.3）——无需数据库。

覆盖：HTTP 桩语义（NOT_IMPLEMENTED 不进熔断）、429/5xx 指数退避重试、
4xx 不重试、熔断开启/恢复、token 预算拦截、embed 形状校验。
真实调用（_post_chat）以 monkeypatch mock，符合 TODO(M1/A) 验收约定。
"""

import pytest

from app.core.errors import AppError
from app.llm.budget import BudgetExceeded
from app.llm.budget import budget as budget_tracker
from app.llm.zhipu import CircuitOpenError, LLMHTTPError, ZhipuProvider, breaker

_OK_RESP = {
    "choices": [{"message": {"content": "{\"items\": []}"}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
}


@pytest.fixture(autouse=True)
def _clean_llm_state():
    """进程内单例状态清理（breaker/budget，与限流器测试同约定）。"""
    breaker.reset()
    budget_tracker.reset()
    yield
    breaker.reset()
    budget_tracker.reset()


def make_provider(monkeypatch) -> ZhipuProvider:
    from app.core.config import Settings

    p = ZhipuProvider(Settings(env="dev", zhipu_api_key="test-key"))
    monkeypatch.setattr(p, "_retry_delay", lambda n: None)  # 免真实 sleep
    return p


def test_stub_not_implemented_by_default(monkeypatch):
    """桩状态：NOT_IMPLEMENTED 原样抛出，不进熔断计数（连续多次仍为桩错误）。"""
    p = make_provider(monkeypatch)
    msgs = [{"role": "user", "content": "hi"}]
    for _ in range(6):  # 超过默认熔断阈值
        with pytest.raises(AppError) as ei:
            p.chat(msgs, purpose="extract")
        assert ei.value.code == "NOT_IMPLEMENTED"
    assert not breaker.is_open()


def test_retry_on_5xx_then_success(monkeypatch):
    p = make_provider(monkeypatch)
    calls = {"n": 0}

    def flaky(payload):
        calls["n"] += 1
        if calls["n"] < 3:
            raise LLMHTTPError(500, "boom")
        return dict(_OK_RESP)

    monkeypatch.setattr(p, "_post_chat", flaky)
    res = p.chat([{"role": "user", "content": "hi"}], purpose="extract")
    assert res.content == "{\"items\": []}"
    assert res.prompt_tokens == 100 and res.output_tokens == 50
    assert calls["n"] == 3  # 首调 + 2 次重试


def test_retry_exhausted_raises(monkeypatch):
    p = make_provider(monkeypatch)
    calls = {"n": 0}

    def always_500(payload):
        calls["n"] += 1
        raise LLMHTTPError(503, "down")

    monkeypatch.setattr(p, "_post_chat", always_500)
    with pytest.raises(LLMHTTPError):
        p.chat([{"role": "user", "content": "hi"}], purpose="extract")
    assert calls["n"] == 4  # 首调 + 3 次重试


def test_4xx_not_retried(monkeypatch):
    p = make_provider(monkeypatch)
    calls = {"n": 0}

    def bad_request(payload):
        calls["n"] += 1
        raise LLMHTTPError(400, "bad payload")

    monkeypatch.setattr(p, "_post_chat", bad_request)
    with pytest.raises(LLMHTTPError):
        p.chat([{"role": "user", "content": "hi"}], purpose="extract")
    assert calls["n"] == 1


def test_circuit_opens_after_consecutive_failures(monkeypatch):
    p = make_provider(monkeypatch)

    def always_500(payload):
        raise LLMHTTPError(500, "down")

    monkeypatch.setattr(p, "_post_chat", always_500)
    for _ in range(5):  # 默认阈值 5
        with pytest.raises(LLMHTTPError):
            p.chat([{"role": "user", "content": "hi"}], purpose="extract")
    assert breaker.is_open()

    calls = {"n": 0}

    def never_called(payload):
        calls["n"] += 1
        return dict(_OK_RESP)

    monkeypatch.setattr(p, "_post_chat", never_called)
    with pytest.raises(CircuitOpenError):
        p.chat([{"role": "user", "content": "hi"}], purpose="extract")
    assert calls["n"] == 0  # 熔断期快速失败，真实调用未发起


def test_circuit_success_resets(monkeypatch):
    p = make_provider(monkeypatch)
    for _ in range(4):
        breaker.record_failure()
    monkeypatch.setattr(p, "_post_chat", lambda payload: dict(_OK_RESP))
    p.chat([{"role": "user", "content": "hi"}], purpose="extract")
    assert breaker._consecutive == 0  # 成功清零


def test_budget_blocks_next_call(monkeypatch):
    p = make_provider(monkeypatch)
    big = dict(_OK_RESP,
               usage={"prompt_tokens": 590_000, "completion_tokens": 20_000})
    monkeypatch.setattr(p, "_post_chat", lambda payload: dict(big))
    # 首次调用成功（610k > 600k 上限在 add 处越限，但本次已发生不回退）
    p.chat([{"role": "user", "content": "hi"}], purpose="extract", task_id=1)
    # 下一次调用发起前被预算拦截
    with pytest.raises(BudgetExceeded):
        p.chat([{"role": "user", "content": "hi"}], purpose="extract", task_id=1)


def test_embed_stub_and_shape_guard(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(AppError) as ei:
        p.embed(["文本"])
    assert ei.value.code == "NOT_IMPLEMENTED"

    def bad_shape(payload):
        return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}  # 维度不符

    monkeypatch.setattr(p, "_post_embed", bad_shape)
    with pytest.raises(LLMHTTPError):
        p.embed(["文本"])


def test_json_mode_sets_response_format(monkeypatch):
    p = make_provider(monkeypatch)
    seen = {}

    def capture(payload):
        seen.update(payload)
        return dict(_OK_RESP)

    monkeypatch.setattr(p, "_post_chat", capture)
    p.chat([{"role": "user", "content": "hi"}], json_mode=True, purpose="extract")
    assert seen["response_format"] == {"type": "json_object"}
    assert seen["model"] == "glm-4.6"  # heavy tier 默认模型（02 §7）

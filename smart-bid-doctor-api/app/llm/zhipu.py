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

    def chat(self, messages, *, json_mode=False, tier="heavy", max_tokens=4096,
             temperature=0.1) -> ChatResult:
        raise AppError(
            ERROR_CODES["NOT_IMPLEMENTED"], "NOT_IMPLEMENTED",
            "LLM 调用未接入（骨架版）——M1 实现见 02-详细设计 §7",
        )

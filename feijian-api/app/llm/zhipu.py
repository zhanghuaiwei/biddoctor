"""智谱 GLM Provider（OpenAI 兼容接口）。
骨架版不实现真实调用——M1 接入抽取/对照时补齐（HTTP 客户端、重试/熔断、llm_calls 记账、budget 上限）。"""

from app.core.errors import AppError
from app.llm.base import ChatResult

BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
TIER_MODEL = {"heavy": "glm-4.6", "light": "glm-4.5-flash"}  # 版本随智谱 lineup 更新，进配置


class ZhipuProvider:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self.api_key = api_key
        self.base_url = base_url

    def chat(self, messages, *, json_mode=False, tier="heavy", max_tokens=4096, temperature=0.1) -> ChatResult:
        raise AppError(501, "NOT_IMPLEMENTED", "LLM 调用未接入（骨架版）——M1 实现见 02-详细设计 §7")

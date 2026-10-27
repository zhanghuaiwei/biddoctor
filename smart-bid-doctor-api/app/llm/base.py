"""LLM Provider 抽象（02 §7）。模型名/版本进配置不进代码。"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatResult:
    content: str
    prompt_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class LLMProvider(Protocol):
    def chat(
        self,
        messages: list[dict],
        *,
        json_mode: bool = False,
        tier: str = "heavy",  # heavy=抽取/判定, light=摘要/兜底（02 §7）
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> ChatResult: ...

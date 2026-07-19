"""LLM 客户端抽象。"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class Message:
    """对话消息。"""

    role: str  # "system" | "user" | "assistant"
    content: str


class ILLMClient(ABC):
    """LLM 客户端接口 — 对话生成。

    实现可以是 DeepSeek、OpenAI、本地 vLLM 等。
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """非流式对话。

        Args:
            messages: 消息列表（含 system/user/assistant 角色）
            temperature: 生成温度
            max_tokens: 最大输出 token

        Returns:
            LLM 回复文本
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """流式对话，逐 token 输出。

        Args:
            messages: 消息列表
            temperature: 生成温度
            max_tokens: 最大输出 token

        Yields:
            每个 token 的文本
        """
        ...

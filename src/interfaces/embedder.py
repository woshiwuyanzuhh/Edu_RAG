"""Embedding 生成器抽象。"""

from abc import ABC, abstractmethod


class IEmbedder(ABC):
    """Embedding 服务抽象 — 文本转向量。

    LLM 和 Embedding 可以使用完全不同的 API 地址，
    例如 LLM 用 DeepSeek，Embedding 用本地 Ollama 的 bge-m3。
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本 Embedding。

        Args:
            texts: 文本列表，建议一次传入全部以利用批处理

        Returns:
            与 texts 等长的向量列表，每个向量为 float 列表
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """嵌入向量维度。"""
        ...

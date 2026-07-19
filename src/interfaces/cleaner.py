"""文本清洗器抽象。"""

from abc import ABC, abstractmethod


class ICleaner(ABC):
    """文本清洗器接口 — 移除噪声、格式化文本。"""

    @abstractmethod
    def clean(self, text: str) -> str:
        """清洗文本（切分前执行）。

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        ...

    @abstractmethod
    def filter_chunks(self, chunks: list[str]) -> list[str]:
        """切分后过滤低质量块、去重。

        Args:
            chunks: 切分后的文本块列表

        Returns:
            过滤后的文本块列表
        """
        ...

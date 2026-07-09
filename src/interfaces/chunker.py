"""文本分块器抽象。"""
from abc import ABC, abstractmethod


class IChunker(ABC):
    """文本分块器接口 — 将长文本切分为语义完整的块。"""

    @abstractmethod
    def split(self, text: str) -> list[str]:
        """将文本切分为块列表。

        Args:
            text: 待切分的纯文本

        Returns:
            文本块列表，每个块应是语义相对完整的单元
        """
        ...

    @property
    @abstractmethod
    def chunk_size(self) -> int:
        """目标块大小（字符数）。"""
        ...

    @property
    @abstractmethod
    def chunk_overlap(self) -> int:
        """块间重叠字符数。"""
        ...

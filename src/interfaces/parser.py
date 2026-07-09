"""文档解析器抽象。"""
from abc import ABC, abstractmethod


class IParser(ABC):
    """文档解析器接口 — 将文件路径转为纯文本。"""

    @abstractmethod
    def parse(self, file_path: str) -> str:
        """解析文件，返回纯文本内容。

        Args:
            file_path: 文件路径

        Returns:
            解析后的纯文本

        Raises:
            ValueError: 文件无法解析或损坏
        """
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """返回支持的文件扩展名集合，如 {'.pdf', '.txt'}。"""
        ...

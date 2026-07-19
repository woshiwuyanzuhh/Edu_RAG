"""查询扩展器抽象。"""

from abc import ABC, abstractmethod


class IQueryExpander(ABC):
    """查询扩展器接口 — 将用户问题改写为多个角度的搜索查询。

    目的：覆盖不同表达方式，提高召回覆盖率。
    """

    @abstractmethod
    async def expand(self, question: str, n: int = 4) -> list[str]:
        """将用户问题扩展为 n 个搜索查询。

        Args:
            question: 原始用户问题
            n: 目标查询数量

        Returns:
            查询列表，始终包含原始问题
        """
        ...

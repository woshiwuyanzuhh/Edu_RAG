"""重排序器抽象。"""
from abc import ABC, abstractmethod
from src.interfaces.vector_store import SearchResult


class IReranker(ABC):
    """重排序器接口 — 对粗排召回结果精排。

    两阶段检索：先粗排（向量检索 Top-K 100~200），
    再精排（Cross-Encoder 或 LLM 打分 Top-N 5~10）。
    """

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """对候选结果重排序，返回 top_k。

        注意：应在返回结果中保留原始向量分数（original_score），
        同时在 score 字段中写入精排分数或融合分数。

        Args:
            query: 用户查询
            candidates: 粗排召回的候选列表
            top_k: 返回数量

        Returns:
            精排后的 top_k 结果，score 为融合分
        """
        ...

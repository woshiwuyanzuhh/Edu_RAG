"""检索服务接口 — Generation 层通过此接口调用检索，不再直接依赖 Retrieval 内部模块。"""
from abc import ABC, abstractmethod

from src.interfaces.vector_store import SearchResult


class IRetrievalService(ABC):
    """检索服务抽象 — 封装 recall + rerank + build_context 完整管线。

    Generation 层和 Orchestration 层只依赖此接口，不 import 任何 src.retrieval.* 内部模块。
    解决问题：架构原则 #4「检索与生成必须解耦，独立迭代」。
    """

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: int | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
        hybrid: bool = False,
    ) -> list[SearchResult]:
        """检索管线：查询扩展 → 粗排召回 → (可选)精排重排 → 返回候选列表。

        Args:
            query: 用户查询
            knowledge_base_id: 限定知识库（None 则搜索全部）
            top_k: 返回数量
            use_rerank: 是否启用 LLM 重排序

        Returns:
            按 score 降序的检索结果列表
        """
        ...

    @abstractmethod
    async def retrieve_with_context(
        self,
        query: str,
        *,
        knowledge_base_id: int | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> dict:
        """检索并构建上下文 — retrieve() + build_context 一步完成。

        解决 Generation 层不需要 import build_context 的问题。

        Returns:
            {"hits": list[SearchResult], "context": str}
        """
        ...

    @abstractmethod
    async def build_context_for_exam(
        self,
        knowledge_base_id: int,
        *,
        max_chunks: int = 10,
    ) -> str:
        """为考试出题构造多角度检索上下文。

        使用多角度查询并行召回（概念/方法/应用），去重合并后拼接为 LLM 可用的文本。

        Args:
            knowledge_base_id: 知识库 ID
            max_chunks: 最多保留的块数

        Returns:
            格式化的上下文文本
        """
        ...

    @abstractmethod
    async def build_bm25(self, documents: list[str]) -> None:
        """构建共享 BM25 关键词索引（由 ingestion 管线在文档上传后调用）。

        应在每次文档上传成功后调用，保持 BM25 索引与向量库同步。
        """
        ...

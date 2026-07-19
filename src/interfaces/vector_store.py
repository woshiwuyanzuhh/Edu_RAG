"""向量数据库抽象。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VectorItem:
    """待插入的向量项。"""

    id: str
    text: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    """统一的 Chunk 类型 — Retrieval 输出和管线输入的标准格式 (Opt-14)。"""

    text: str
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"text": self.text, "score": self.score, "metadata": self.metadata}


@dataclass
class SearchResult:
    """检索结果项。"""

    id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)

    def to_chunk(self) -> "Chunk":
        """转换为统一 Chunk 类型 (Opt-14)。"""
        return Chunk(text=self.text, score=self.score, metadata=self.metadata)


class IVectorStore(ABC):
    """向量数据库接口 — 存储与相似度检索。

    实现可以是 Milvus（分布式）、
    Pinecone（云服务）等，上层代码不感知差异。
    """

    @abstractmethod
    async def insert(self, items: list[VectorItem]) -> None:
        """批量插入向量。

        Args:
            items: 向量项列表
        """
        ...

    @abstractmethod
    async def search(
        self,
        query: list[float],
        top_k: int = 5,
        filter_expr: dict | None = None,
    ) -> list[SearchResult]:
        """相似度检索。

        Args:
            query: 查询向量
            top_k: 返回数量
            filter_expr: 可选的过滤条件（如 {"knowledge_base_id": 1}）

        Returns:
            按相似度降序排列的检索结果
        """
        ...

    @abstractmethod
    async def delete_by_ids(self, ids: list[str]) -> None:
        """按 ID 删除向量。

        Args:
            ids: 向量 ID 列表
        """
        ...

    @abstractmethod
    async def delete_by_filter(self, filter_expr: dict) -> None:
        """按过滤条件批量删除。

        Args:
            filter_expr: 过滤条件
        """
        ...

    @abstractmethod
    async def connect(self) -> None:
        """连接向量数据库（在应用启动时调用）。"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接（在应用关闭时调用）。"""
        ...

    @abstractmethod
    async def count(self) -> int:
        """返回向量总数。"""
        ...

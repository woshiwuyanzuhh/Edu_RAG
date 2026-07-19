"""Ingestion 服务接口 — Ingress 层唯一对外门面。

Orchestration 层通过此接口调用文档写入管线，不直接依赖 ingress 内部模块。

解决问题：原则 #2 — 每层必须且只能暴露一个 Facade 接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class IngestionResult:
    """写入管线结果。"""

    chunks: list[dict] = field(default_factory=list)  # [{text, chunk_index, metadata}]
    total_chars: int = 0
    original_chars: int = 0
    chunk_count: int = 0
    stats: dict = field(default_factory=dict)


class IIngestionService(ABC):
    """Ingestion 服务抽象 — 封装文档写入完整管线。

    Orchestration 层只依赖此接口，不 import 任何 src.ingress.* 内部模块。
    """

    @abstractmethod
    async def ingest(
        self,
        file_path: str,
        doc_id: int,
        kb_id: int,
        *,
        doc_type: str = "general",
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ) -> IngestionResult:
        """执行完整文档写入管线。

        流程：parse → clean → chunk → filter → embed → vector_insert → bm25_build

        Args:
            file_path: 文件路径
            doc_id: 文档 ID（MySQL 中的记录）
            kb_id: 知识库 ID
            doc_type: 文档类型 (general / education / gaming)
            chunk_size: 目标块大小
            chunk_overlap: 块间重叠

        Returns:
            IngestionResult: 包含 chunk 列表和统计信息
        """
        ...

    @abstractmethod
    async def delete_document(self, doc_id: int, kb_id: int, file_path: str) -> None:
        """删除文档 — 清理向量库中的向量 + 失效缓存。

        Args:
            doc_id: 文档 ID
            kb_id: 知识库 ID
            file_path: 文件路径（用于删除物理文件）
        """
        ...

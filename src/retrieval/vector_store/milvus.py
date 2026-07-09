"""Milvus 向量存储实现 — 生产级分布式向量检索。

使用 pymilvus 客户端 (gRPC)，通过 asyncio.to_thread() 异步桥接。

前置条件:
    pip install pymilvus>=2.4
    Milvus 服务运行中 (docker compose up milvus-standalone)
"""
import asyncio
import logging
from typing import Any

from src.interfaces.vector_store import IVectorStore, VectorItem, SearchResult
from src.shared.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "edu_docs"
DIM = 1024  # bge-m3 维度

# 延迟导入避免强制依赖
try:
    from pymilvus import (
        connections, Collection, FieldSchema, CollectionSchema, DataType, utility,
    )
    _HAS_PYMILVUS = True
except ImportError:
    _HAS_PYMILVUS = False


class MilvusStore(IVectorStore):
    """Milvus 向量数据库 — 支持 HNSW 索引 + COSINE 相似度 + knowledge_base_id 过滤。"""

    def __init__(self):
        if not _HAS_PYMILVUS:
            raise ImportError(
                "pymilvus 未安装。请执行: pip install pymilvus>=2.4"
            )
        self._collection: Any = None
        self._connected = False

    async def connect(self) -> None:
        """连接 Milvus 并创建/加载 Collection。"""
        await asyncio.to_thread(
            connections.connect,
            alias="default",
            host=settings.vector_store.milvus_host,
            port=settings.vector_store.milvus_port,
        )

        if utility.has_collection(COLLECTION_NAME):
            self._collection = Collection(COLLECTION_NAME)
        else:
            self._collection = await self._create_collection()

        await asyncio.to_thread(self._collection.load)
        self._connected = True
        logger.info(f"milvus_connected host={settings.vector_store.milvus_host} "
                     f"port={settings.vector_store.milvus_port} count={await self.count()}")

    async def _create_collection(self) -> Any:
        schema = CollectionSchema(
            fields=[
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
                FieldSchema(name="knowledge_base_id", dtype=DataType.INT64),
                FieldSchema(name="doc_id", dtype=DataType.INT64),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
            ],
            description="edu_rag document chunks",
        )
        col = Collection(COLLECTION_NAME, schema)
        # HNSW 索引
        col.create_index(
            field_name="embedding",
            index_params={"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}},
        )
        return col

    async def disconnect(self) -> None:
        if self._connected:
            await asyncio.to_thread(connections.disconnect, "default")
            self._connected = False

    # ── IVectorStore 实现 ──

    async def insert(self, items: list[VectorItem]) -> None:
        if not items or not self._collection:
            return
        data = [[], [], [], [], [], []]
        for item in items:
            data[0].append(item.id)
            data[1].append(item.text)
            data[2].append(item.embedding)
            data[3].append(item.metadata.get("knowledge_base_id", 0))
            data[4].append(item.metadata.get("doc_id", 0))
            data[5].append(item.metadata.get("chunk_index", 0))

        await asyncio.to_thread(self._collection.insert, data)
        await asyncio.to_thread(self._collection.flush)
        logger.debug(f"milvus_insert count={len(items)}")

    async def search(
        self, query: list[float], top_k: int = 5, filter_expr: dict | None = None,
    ) -> list[SearchResult]:
        if not self._collection:
            return []

        expr = self._build_expr(filter_expr)
        search_params = {"metric_type": "COSINE", "params": {"ef": 64}}

        try:
            results = await asyncio.to_thread(
                self._collection.search,
                data=[query],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["text", "knowledge_base_id", "doc_id", "chunk_index"],
            )
        except Exception as e:
            logger.error(f"milvus_search_failed error={e}")
            return []

        hits = []
        if results:
            for hit in results[0]:
                hits.append(SearchResult(
                    id=str(hit.id),
                    text=hit.entity.get("text", ""),
                    score=round(hit.distance, 4),
                    metadata={
                        "doc_id": hit.entity.get("doc_id", 0),
                        "chunk_index": hit.entity.get("chunk_index", 0),
                        "knowledge_base_id": hit.entity.get("knowledge_base_id", 0),
                    },
                ))
        return hits

    async def delete_by_ids(self, ids: list[str]) -> None:
        if not ids or not self._collection:
            return
        expr = f'id in [{", ".join(repr(i) for i in ids)}]'
        await asyncio.to_thread(self._collection.delete, expr)

    async def delete_by_filter(self, filter_expr: dict) -> None:
        if not self._collection:
            return
        expr = self._build_expr(filter_expr)
        if expr:
            await asyncio.to_thread(self._collection.delete, expr)

    async def count(self) -> int:
        if not self._collection:
            return 0
        return await asyncio.to_thread(self._collection.num_entities)

    @staticmethod
    def _build_expr(filter_expr: dict | None) -> str | None:
        if not filter_expr:
            return None
        parts = []
        if "knowledge_base_id" in filter_expr:
            parts.append(f'knowledge_base_id == {filter_expr["knowledge_base_id"]}')
        if "doc_id" in filter_expr:
            parts.append(f'doc_id == {filter_expr["doc_id"]}')
        return " and ".join(parts) if parts else None

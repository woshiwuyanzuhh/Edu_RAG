"""
ChromaDB 向量存储实现。

解决问题 #9: 文件名/配置名不再混淆 Milvus。
解决问题 #17: 路径使用绝对路径 PROJECT_ROOT/data/chroma，消除 CWD 依赖。
"""
import uuid
import logging
import chromadb
from chromadb.config import Settings as ChromaSettings

from src.interfaces.vector_store import IVectorStore, VectorItem, SearchResult
from src.shared.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "edu_docs"


class ChromaStore(IVectorStore):
    """ChromaDB PersistentClient 实现。"""

    def __init__(self):
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None

    async def connect(self) -> None:
        """连接（应在 lifespan 中调用）。"""
        path = settings.vector_store.get_chroma_path()
        self._client = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"chroma_connected path={path} count={self._collection.count()}")

    async def disconnect(self) -> None:
        self._client = None
        self._collection = None

    # ── IVectorStore 实现 ──

    async def insert(self, items: list[VectorItem]) -> None:
        if not items or not self._collection:
            return

        ids = [item.id or uuid.uuid4().hex for item in items]
        texts = [item.text for item in items]
        embeddings = [item.embedding for item in items]
        metadatas = [item.metadata for item in items]

        self._collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        logger.debug(f"chroma_insert count={len(items)}")

    async def search(
        self,
        query: list[float],
        top_k: int = 5,
        filter_expr: dict | None = None,
    ) -> list[SearchResult]:
        if not self._collection:
            return []

        where = None
        if filter_expr:
            where = dict(filter_expr)
            unknown = set(filter_expr.keys()) - {"knowledge_base_id"}
            if unknown:
                logger.warning(f"chroma_search_unknown_filter keys={unknown} — only 'knowledge_base_id' is supported")

        results = self._collection.query(
            query_embeddings=[query],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                distance = results["distances"][0][i] if results.get("distances") else 0
                score = 1.0 - distance  # cosine distance → similarity
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                hits.append(SearchResult(
                    id=results["ids"][0][i],
                    text=results["documents"][0][i] if results.get("documents") else "",
                    score=round(score, 4),
                    metadata=metadata,
                ))

        return hits

    async def delete_by_ids(self, ids: list[str]) -> None:
        if not ids or not self._collection:
            return
        # 分批删除（ChromaDB 限制）
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            self._collection.delete(ids=batch)

    async def delete_by_filter(self, filter_expr: dict) -> None:
        if not self._collection:
            return
        # 分批获取 → 删除
        batch_size = 5000
        while True:
            results = self._collection.get(where=filter_expr, limit=batch_size)
            if not results["ids"]:
                break
            self._collection.delete(ids=results["ids"])

    async def count(self) -> int:
        if not self._collection:
            return 0
        return self._collection.count()

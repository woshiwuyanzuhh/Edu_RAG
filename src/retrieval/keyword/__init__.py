"""Keyword retrieval indexes used by hybrid retrieval.

BM25 indexes are kept per knowledge base to avoid cross-KB result leakage.
The old global API is preserved by treating ``knowledge_base_id=None`` as the
legacy shared index.

P0-C3: BM25 索引持久化到 MySQL ``bm25_index_cache`` 表，支持多实例共享与崩溃恢复。
- 写操作（build/delete/clear）后 fire-and-forget 异步落盘
- 启动时 ``load_all_bm25_from_db()`` 从 MySQL 加载重建
- knowledge_base_id=None（legacy 全局）在表中以 0 存储
"""

import asyncio
import logging

from sqlalchemy import select

from src.retrieval.keyword.bm25 import BM25Index

logger = logging.getLogger(__name__)

_bm25_indexes: dict[int | None, BM25Index] = {}

# knowledge_base_id=None（legacy 全局）在持久化层的映射键
_LEGACY_GLOBAL_KB_KEY = 0


def _kb_to_db_key(knowledge_base_id: int | None) -> int:
    """内存中的 kb_id（None=legacy 全局）→ 持久化主键（0=legacy 全局）。"""
    return knowledge_base_id if knowledge_base_id is not None else _LEGACY_GLOBAL_KB_KEY


def _db_key_to_kb(db_key: int) -> int | None:
    """持久化主键 → 内存 kb_id。"""
    return None if db_key == _LEGACY_GLOBAL_KB_KEY else db_key


async def persist_bm25_to_db(knowledge_base_id: int | None) -> None:
    """将指定知识库的 BM25 索引持久化到 MySQL（upsert / delete）。"""
    from src.shared.database.mysql import _session_factory
    from src.shared.models.orm import BM25IndexCache

    if _session_factory is None:
        return  # MySQL 未初始化，跳过

    idx = _bm25_indexes.get(knowledge_base_id)
    db_key = _kb_to_db_key(knowledge_base_id)

    async with _session_factory() as session:
        existing = await session.get(BM25IndexCache, db_key)
        if idx is None:
            # 内存中已无此索引，删除持久化记录
            if existing is not None:
                await session.delete(existing)
                await session.commit()
            return
        state = idx.to_state()
        if existing is None:
            session.add(
                BM25IndexCache(
                    knowledge_base_id=db_key,
                    docs=state["docs"],
                    metadatas=state["metadatas"],
                )
            )
        else:
            existing.docs = state["docs"]
            existing.metadatas = state["metadatas"]
        await session.commit()


async def load_all_bm25_from_db() -> int:
    """启动时从 MySQL 加载所有 BM25 索引到内存。返回加载数量。"""
    from src.shared.database.mysql import _session_factory
    from src.shared.models.orm import BM25IndexCache

    if _session_factory is None:
        logger.warning("bm25_load_skipped mysql_not_initialized")
        return 0

    count = 0
    async with _session_factory() as session:
        result = await session.execute(select(BM25IndexCache))
        for row in result.scalars():
            kb_id = _db_key_to_kb(row.knowledge_base_id)
            try:
                idx = BM25Index()
                idx.from_state({"docs": row.docs or [], "metadatas": row.metadatas or []})
                _bm25_indexes[kb_id] = idx
                count += 1
            except Exception as e:
                logger.warning(f"bm25_load_failed kb={kb_id} error={e}")

    logger.info(f"bm25_loaded_from_db count={count}")
    return count


def _schedule_persist(knowledge_base_id: int | None) -> None:
    """触发异步持久化（fire-and-forget，失败仅告警，不阻塞调用方）。"""
    try:
        asyncio.create_task(persist_bm25_to_db(knowledge_base_id))
    except RuntimeError:
        # 无运行中的 event loop（如启动期同步上下文），跳过
        logger.debug("bm25_persist_skipped_no_loop")


def get_bm25(knowledge_base_id: int | None = None) -> BM25Index | None:
    """Return the BM25 index for a knowledge base, or the legacy global index."""
    return _bm25_indexes.get(knowledge_base_id)


def build_bm25(
    documents: list[str],
    *,
    knowledge_base_id: int | None = None,
    metadatas: list[dict] | None = None,
    append: bool = False,
) -> BM25Index | None:
    """Build or update a shared BM25 index.

    Args:
        documents: Text chunks to index.
        knowledge_base_id: Knowledge base scope. ``None`` keeps legacy global behavior.
        metadatas: Optional metadata aligned with ``documents``.
        append: Append chunks to the existing scoped index instead of rebuilding it.
    """
    try:
        idx = _bm25_indexes.get(knowledge_base_id)
        if idx is None:
            idx = BM25Index()
            _bm25_indexes[knowledge_base_id] = idx

        if append:
            metadata_items = metadatas or [{} for _ in documents]
            if len(metadata_items) != len(documents):
                raise ValueError("metadatas length must match documents length")
            for doc, metadata in zip(documents, metadata_items, strict=True):
                idx.add(doc, metadata)
        else:
            idx.build(documents, metadatas)
        _schedule_persist(knowledge_base_id)  # P0-C3: 异步落盘
        return idx
    except ImportError:
        logger.warning("rank_bm25 未安装，BM25 关键词检索不可用")
        return None


def delete_bm25_documents(*, knowledge_base_id: int, doc_id: int) -> int:
    """Remove all chunks for a document from its scoped BM25 index."""
    idx = _bm25_indexes.get(knowledge_base_id)
    if idx is None:
        return 0
    removed = idx.remove_where(lambda metadata: metadata.get("doc_id") == doc_id)
    if idx.doc_count == 0:
        _bm25_indexes.pop(knowledge_base_id, None)
    _schedule_persist(knowledge_base_id)  # P0-C3: 异步落盘（含清空场景）
    return removed


def clear_bm25(knowledge_base_id: int | None = None) -> None:
    """Clear one scoped index. ``None`` clears the legacy global index."""
    _bm25_indexes.pop(knowledge_base_id, None)
    _schedule_persist(knowledge_base_id)  # P0-C3: 异步删除持久化记录


__all__ = [
    "BM25Index",
    "build_bm25",
    "clear_bm25",
    "delete_bm25_documents",
    "get_bm25",
    "load_all_bm25_from_db",
    "persist_bm25_to_db",
]

"""
粗排召回模块 — 两阶段检索的第一阶段。

流程:
    查询扩展 → 批量 Embedding → 并发向量检索 → 合并去重 → 返回 Top-K 候选

解决问题 #15: 所有 query 一次性发送给 embedder.embed()，而非逐个调用。
"""

import asyncio
import logging

from src.interfaces.embedder import IEmbedder
from src.interfaces.query_expander import IQueryExpander
from src.interfaces.vector_store import IVectorStore, SearchResult
from src.shared.config import settings

logger = logging.getLogger(__name__)


async def recall(
    query: str,
    embedder: IEmbedder,
    vector_store: IVectorStore,
    expander: IQueryExpander | None = None,
    top_k: int = 5,
    knowledge_base_id: int | None = None,
    recall_multiplier: int | None = None,
) -> list[SearchResult]:
    """粗排召回 — 多 Query 扩展 + 并发向量检索。

    Args:
        query: 用户查询
        embedder: Embedding 服务
        vector_store: 向量数据库
        expander: 查询扩展器（None 则跳过扩展）
        top_k: 每个 query 的检索数量
        knowledge_base_id: 限定知识库
        recall_multiplier: 扩展 query 数量（如 4 → 召回 top_k*4 候选）

    Returns:
        去重合并后的候选列表（按 score 降序）
    """
    # 1. 查询扩展
    if recall_multiplier is None:
        recall_multiplier = settings.retrieval.recall_multiplier
    if expander:
        queries = await expander.expand(query, n=recall_multiplier)
    else:
        queries = [query]

    logger.debug(f"recall_queries count={len(queries)}")

    # 2. 批量生成 embedding（解决问题 #15: 一次 API 调用）
    embeddings = await embedder.embed(queries)

    # 3. 并发检索
    filter_expr = {"knowledge_base_id": knowledge_base_id} if knowledge_base_id else None

    async def _search_one(emb: list[float]) -> list[SearchResult]:
        return await vector_store.search(query=emb, top_k=top_k, filter_expr=filter_expr)

    all_results = await asyncio.gather(*[_search_one(emb) for emb in embeddings])

    # 4. 合并去重（按 text 前 120 字符判重）
    seen: set[str] = set()
    merged: list[SearchResult] = []
    for hits in all_results:
        for h in hits:
            key = (h.text or "")[:120]
            if key not in seen:
                seen.add(key)
                merged.append(h)

    # 5. 按 score 降序
    merged.sort(key=lambda x: x.score, reverse=True)

    logger.info(f"recall_complete query={query[:50]} expanded={len(queries)} hits={len(merged)}")
    return merged

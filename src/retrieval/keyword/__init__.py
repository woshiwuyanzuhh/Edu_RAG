"""关键词检索模块 — BM25 实现，用于混合检索的双路召回。

变更 (P0-2): 新增全局单例管理，解决 BM25 索引在 ingestion 管线构建后
RetrievalService 可共享使用的问题。
"""
from src.retrieval.keyword.bm25 import BM25Index

# 全局 BM25 单例 — 由 ingestion 构建，retrieval 查询
_bm25_index: BM25Index | None = None


def get_bm25() -> BM25Index | None:
    """获取共享 BM25 索引实例。"""
    return _bm25_index


def build_bm25(documents: list[str]) -> BM25Index | None:
    """构建（或重建）共享 BM25 索引。

    Returns:
        BM25Index 实例，或 None（如果 rank_bm25 未安装）。
    """
    global _bm25_index
    try:
        if _bm25_index is None:
            _bm25_index = BM25Index()
        _bm25_index.build(documents)
        return _bm25_index
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("rank_bm25 未安装，BM25 关键词检索不可用")
        return None


__all__ = ["BM25Index", "get_bm25", "build_bm25"]

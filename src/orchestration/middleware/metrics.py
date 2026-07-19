"""Prometheus 业务指标 — 向后兼容 re-export。

⚠️ 指标定义已迁移到 src.observability.metrics（修复分层违规：
    providers/retrieval 层不应依赖 orchestration/middleware）。

请改为直接导入:
    from src.observability.metrics import QA_REQUESTS, RETRIEVAL_LATENCY
"""

from src.observability.metrics import (  # noqa: F401
    ACTIVE_SESSIONS,
    BM25_INDEX_DOCS,
    DOCUMENT_PROCESSED,
    EXAM_REQUESTS,
    LLM_LATENCY,
    QA_REQUESTS,
    RETRIEVAL_LATENCY,
    VECTOR_STORE_TOTAL,
)

__all__ = [
    "QA_REQUESTS",
    "EXAM_REQUESTS",
    "DOCUMENT_PROCESSED",
    "RETRIEVAL_LATENCY",
    "LLM_LATENCY",
    "BM25_INDEX_DOCS",
    "VECTOR_STORE_TOTAL",
    "ACTIVE_SESSIONS",
]

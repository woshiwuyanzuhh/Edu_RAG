"""Prometheus 业务指标定义（P2-C10）。

prometheus_fastapi_instrumentator 自动收集 HTTP 层指标（请求数/延迟/状态码），
本模块定义业务层指标，在关键路径埋点或 lifespan 周期更新。

架构说明：
    指标定义属于 observability 层（可被所有层依赖），
    不放在 orchestration/middleware 下（那会违反分层原则：
    providers/retrieval 不能依赖 orchestration）。

埋点方式：
    from src.observability.metrics import QA_REQUESTS, RETRIEVAL_LATENCY
    QA_REQUESTS.labels(knowledge_base_id=kb_id, status="ok").inc()
    with RETRIEVAL_LATENCY.labels(stage="vector").time():
        results = await vector_store.search(...)
"""
from prometheus_client import Counter, Gauge, Histogram

# ── 请求计数（按业务维度）──
QA_REQUESTS = Counter(
    "edu_rag_qa_requests_total",
    "QA 问答请求总数",
    ["knowledge_base_id", "status"],
)
EXAM_REQUESTS = Counter(
    "edu_rag_exam_requests_total",
    "考试出题/答题请求总数",
    ["question_type", "action"],
)
DOCUMENT_PROCESSED = Counter(
    "edu_rag_document_processed_total",
    "文档处理总数（入库完成/失败）",
    ["status"],
)

# ── 延迟分布（直方图，自动暴露 P50/P90/P99）──
RETRIEVAL_LATENCY = Histogram(
    "edu_rag_retrieval_latency_seconds",
    "检索阶段延迟",
    ["stage"],  # stage: vector / keyword / fusion
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
LLM_LATENCY = Histogram(
    "edu_rag_llm_latency_seconds",
    "LLM 调用延迟",
    ["model"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# ── 资源水位（Gauge，lifespan 周期更新或业务路径设置）──
BM25_INDEX_DOCS = Gauge(
    "edu_rag_bm25_index_docs",
    "BM25 索引文档数",
    ["knowledge_base_id"],
)
VECTOR_STORE_TOTAL = Gauge(
    "edu_rag_vector_store_total",
    "向量库文档总数",
)
ACTIVE_SESSIONS = Gauge(
    "edu_rag_active_sessions",
    "活跃会话数",
)

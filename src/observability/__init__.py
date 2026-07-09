"""可观测性 — 全链路追踪 + RAG 质量指标。

原则 (来自系统架构设计准则 #8):
    全链路追踪（Query → 检索结果 → 拼接上下文 → 生成输出）
    和量化评估（RAGAS、人工标注）是前提。
"""
import time
import uuid
import contextvars
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# ── 请求上下文（跨层传播）──

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def set_request_id(request_id: str | None = None) -> str:
    """设置当前请求 ID。"""
    rid = request_id or uuid.uuid4().hex[:12]
    _request_id.set(rid)
    return rid


def get_request_id() -> str:
    return _request_id.get() or "unknown"


# ── 链路追踪 ──

class TraceSpan:
    """单个追踪 Span — 记录一个阶段的耗时和元数据。"""

    def __init__(self, name: str, parent: "TraceSpan | None" = None):
        self.name = name
        self.span_id = uuid.uuid4().hex[:8]
        self.parent = parent
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.metadata: dict = {}

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time > 0 else 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "span_id": self.span_id,
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
        }


class Tracer:
    """全链路追踪器 — 支持 async context manager。

    用法：
        tracer = Tracer(query="什么是RAG")
        async with tracer.span("recall"):
            hits = await recall(...)
            span.metadata["hit_count"] = len(hits)
        tracer.log_report()  # 输出结构化日志
    """

    def __init__(self, query: str = ""):
        self.trace_id = uuid.uuid4().hex[:16]
        self.query = query
        self.spans: list[TraceSpan] = []
        self._current: TraceSpan | None = None

    @asynccontextmanager
    async def span(self, name: str):
        s = self.start_span(name)
        try:
            yield s
        finally:
            self.end_span(s)

    def start_span(self, name: str) -> TraceSpan:
        span = TraceSpan(name, parent=self._current)
        span.start_time = time.perf_counter()
        self._current = span
        return span

    def end_span(self, span: TraceSpan) -> None:
        span.end_time = time.perf_counter()
        self.spans.append(span)
        self._current = span.parent

    def report(self) -> dict:
        total_ms = sum(s.duration_ms for s in self.spans)
        return {
            "trace_id": self.trace_id,
            "request_id": get_request_id(),
            "query": self.query[:100],
            "total_ms": round(total_ms, 2),
            "spans": [s.to_dict() for s in self.spans],
        }

    def log_report(self) -> None:
        report_data = self.report()
        logger.info(f"trace_report trace_id={report_data['trace_id']} request_id={report_data['request_id']} "
                    f"query={report_data['query']} total_ms={report_data['total_ms']} spans={len(report_data['spans'])}")


# ── RAGAS 评估指标 ──

def compute_retrieval_precision(
    retrieved_ids: list[str],
    relevant_ids: list[str],
) -> float:
    """检索精度: 检索结果中相关文档的比例。"""
    if not retrieved_ids:
        return 0.0
    relevant_set = set(relevant_ids)
    return sum(1 for rid in retrieved_ids if rid in relevant_set) / len(retrieved_ids)


def compute_answer_faithfulness(answer: str, context: str) -> float:
    """
    答案忠实度（简化版）— 字符重叠比例。生产环境请使用 evaluate_rag()。
    """
    if not answer.strip() or not context.strip():
        return 0.0
    answer_chars = set(answer.replace(" ", ""))
    context_chars = set(context.replace(" ", ""))
    if not answer_chars:
        return 0.0
    return len(answer_chars & context_chars) / len(answer_chars)


def evaluate_rag(
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None = None,
) -> dict:
    """RAGAS 评估 — 回答忠实度 + 上下文相关性 + (可选)事实正确性。

    首次调用会自动下载 RAGAS 模型（~200MB），后续调用使用缓存。

    Args:
        question: 用户问题
        answer: RAG 生成的回答
        contexts: 检索召回的上下文列表
        ground_truth: 参考答案（可选，用于计算 AnswerCorrectness）

    Returns:
        {"faithfulness": float, "context_relevancy": float, "answer_correctness": float | None}
        所有值在 [0, 1] 之间。
    """
    from ragas.metrics import Faithfulness, ContextRelevancy, AnswerCorrectness
    from ragas import SingleTurnSample

    metrics: dict = {}
    sample = SingleTurnSample(
        user_input=question,
        response=answer,
        retrieved_contexts=contexts,
        reference=ground_truth or "",
    )

    try:
        metrics["faithfulness"] = float(Faithfulness().single_turn_score(sample))
    except Exception:
        metrics["faithfulness"] = 0.0

    try:
        metrics["context_relevancy"] = float(ContextRelevancy().single_turn_score(sample))
    except Exception:
        metrics["context_relevancy"] = 0.0

    if ground_truth:
        try:
            metrics["answer_correctness"] = float(AnswerCorrectness().single_turn_score(sample))
        except Exception:
            metrics["answer_correctness"] = 0.0
    else:
        metrics["answer_correctness"] = None

    return metrics

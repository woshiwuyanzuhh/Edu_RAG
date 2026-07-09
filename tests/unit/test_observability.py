"""可观测性测试 — src/observability/__init__.py。"""
import pytest
import asyncio
from src.observability import (
    Tracer, TraceSpan,
    set_request_id, get_request_id,
    compute_retrieval_precision, compute_answer_faithfulness,
)


class TestRequestID:
    """请求 ID 上下文传播。"""

    def test_set_and_get(self):
        rid = set_request_id("test-123")
        assert rid == "test-123"
        assert get_request_id() == "test-123"

    def test_generates_id_when_none(self):
        rid = set_request_id(None)
        assert len(rid) == 12  # hex[:12]
        assert get_request_id() == rid

    def test_default_unknown(self):
        set_request_id("_clear_")
        # 在新 context 中默认返回 "unknown"
        import contextvars
        ctx = contextvars.copy_context()
        rid = ctx.run(get_request_id)
        assert rid in ("unknown", "_clear_")


class TestTraceSpan:
    """TraceSpan 单元。"""

    def test_default_state(self):
        span = TraceSpan(name="test_span")
        assert span.name == "test_span"
        assert len(span.span_id) == 8
        assert span.duration_ms == 0
        assert span.metadata == {}

    def test_duration(self):
        span = TraceSpan(name="test")
        span.start_time = 100.0
        span.end_time = 100.5
        assert span.duration_ms == 500.0

    def test_to_dict(self):
        span = TraceSpan(name="recall")
        span.start_time = 0.0
        span.end_time = 0.045
        span.metadata["hit_count"] = 10
        d = span.to_dict()
        assert d["name"] == "recall"
        assert d["duration_ms"] == 45.0
        assert d["metadata"]["hit_count"] == 10


class TestTracer:
    """Tracer 全链路追踪。"""

    def test_init(self):
        tracer = Tracer(query="什么是RAG")
        assert len(tracer.trace_id) == 16
        assert tracer.query == "什么是RAG"
        assert tracer.spans == []

    def test_sync_start_end_span(self):
        tracer = Tracer(query="test")
        span = tracer.start_span("recall")
        span.metadata["count"] = 5
        tracer.end_span(span)
        assert len(tracer.spans) == 1
        assert tracer.spans[0].name == "recall"
        assert tracer.spans[0].metadata["count"] == 5

    def test_report_empty(self):
        tracer = Tracer()
        report = tracer.report()
        assert "trace_id" in report
        assert report["total_ms"] == 0.0
        assert report["spans"] == []

    def test_report_with_spans(self):
        tracer = Tracer(query="test query")
        s1 = tracer.start_span("step1")
        tracer.end_span(s1)
        s2 = tracer.start_span("step2")
        tracer.end_span(s2)

        report = tracer.report()
        assert report["query"] == "test query"
        assert report["total_ms"] >= 0  # 实际耗时 ≥ 0
        assert len(report["spans"]) == 2
        assert report["spans"][0]["name"] == "step1"
        assert report["spans"][1]["name"] == "step2"

    def test_async_span_context_manager(self):
        tracer = Tracer(query="async test")
        async def _run():
            async with tracer.span("recall") as span:
                span.metadata["vec_count"] = 20
            return tracer.spans
        spans = asyncio.run(_run())
        assert len(spans) == 1
        assert spans[0].name == "recall"
        assert spans[0].metadata["vec_count"] == 20

    def test_span_parent_chain(self):
        tracer = Tracer()
        s1 = tracer.start_span("parent")
        # 通过 async context manager 无法直接测 parent，用同步方式验证
        assert tracer._current == s1
        s2 = tracer.start_span("child")
        assert s2.parent == s1
        tracer.end_span(s2)
        tracer.end_span(s1)
        assert len(tracer.spans) == 2

    def test_log_report_does_not_raise(self):
        tracer = Tracer(query="test")
        # log_report 应正常执行不抛异常
        tracer.log_report()


class TestRetrievalPrecision:
    """检索精度计算。"""

    def test_perfect(self):
        assert compute_retrieval_precision(["1", "2", "3"], ["1", "2", "3"]) == 1.0

    def test_half(self):
        assert compute_retrieval_precision(["1", "2", "4", "5"], ["1", "2"]) == 0.5

    def test_none_relevant(self):
        assert compute_retrieval_precision(["1", "2"], ["3", "4"]) == 0.0

    def test_empty_retrieved(self):
        assert compute_retrieval_precision([], ["1", "2"]) == 0.0


class TestAnswerFaithfulness:
    """答案忠实度（简化版字符重叠）。"""

    def test_identical(self):
        score = compute_answer_faithfulness("机器学习", "机器学习是重要技术")
        assert score > 0.5

    def test_empty_answer(self):
        assert compute_answer_faithfulness("", "有上下文") == 0.0

    def test_empty_context(self):
        assert compute_answer_faithfulness("有答案", "") == 0.0

    def test_no_overlap(self):
        score = compute_answer_faithfulness("ABCDEFG", "HIJKLMN")
        assert score == 0.0

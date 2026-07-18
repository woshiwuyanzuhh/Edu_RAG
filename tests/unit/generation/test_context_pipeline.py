"""上下文增强管线单元测试 — src/generation/context/。

覆盖：
    - LostInMiddleReorder: 注意力重排（纯逻辑）
    - ContextPipeline: 步骤链执行引擎
    - RelevanceFilter: LLM 相关性过滤（mock LLM）
    - SemanticCompressor: LLM 语义压缩（mock LLM）
"""
import pytest
import asyncio
import json

from src.interfaces.llm import ILLMClient, Message
from src.generation.context.pipeline import ContextPipeline
from src.generation.context.lost_middle import LostInMiddleReorder
from src.generation.context.relevance_filter import RelevanceFilter
from src.generation.context.compressor import SemanticCompressor


# ── Mock LLM ──

class MockLLMClient(ILLMClient):
    """可编程的 LLM mock — 按序返回预设响应。"""

    def __init__(self, responses: list[str] | str = "mock"):
        self._responses = responses if isinstance(responses, list) else [responses]
        self._idx = 0
        self.calls: list[list[Message]] = []

    async def chat(self, messages, temperature=0.7, max_tokens=2048) -> str:
        self.calls.append(messages)
        if self._idx < len(self._responses):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp
        return self._responses[-1]

    async def chat_stream(self, messages, temperature=0.7, max_tokens=2048):
        for token in ["mock", "stream"]:
            yield token


def _chunk(text: str, score: float = 0.5) -> dict:
    return {"text": text, "score": score, "metadata": {}}


# ── LostInMiddleReorder ──

class TestLostInMiddleReorder:
    def test_empty_returns_empty(self):
        reorder = LostInMiddleReorder()
        result = asyncio.run(reorder.process([], "query"))
        assert result == []

    def test_leq_three_unchanged_order(self):
        reorder = LostInMiddleReorder()
        chunks = [_chunk("a", 0.9), _chunk("b", 0.8), _chunk("c", 0.7)]
        result = asyncio.run(reorder.process(chunks, "query"))
        assert len(result) == 3
        # ≤3 直接返回副本，顺序不变
        assert result[0]["text"] == "a"

    def test_reorder_best_head_second_best_tail(self):
        reorder = LostInMiddleReorder()
        chunks = [
            _chunk("best", 0.9),
            _chunk("second", 0.8),
            _chunk("mid1", 0.5),
            _chunk("mid2", 0.4),
            _chunk("mid3", 0.3),
        ]
        result = asyncio.run(reorder.process(chunks, "query"))
        assert len(result) == 5
        assert result[0]["text"] == "best"       # 最高分 → 头部
        assert result[-1]["text"] == "second"    # 次高分 → 尾部
        # 中间 3 个保持原序（已按 score 降序）
        assert result[1]["text"] == "mid1"

    def test_does_not_mutate_input(self):
        reorder = LostInMiddleReorder()
        chunks = [_chunk("a", 0.9), _chunk("b", 0.8), _chunk("c", 0.7), _chunk("d", 0.6)]
        original = list(chunks)
        asyncio.run(reorder.process(chunks, "query"))
        assert chunks == original


# ── ContextPipeline ──

class TestContextPipeline:
    def test_empty_pipeline_returns_input(self):
        pipeline = ContextPipeline([])
        chunks = [_chunk("a"), _chunk("b")]
        result = asyncio.run(pipeline.process(chunks, "query"))
        assert result == chunks

    def test_empty_chunks_short_circuit(self):
        pipeline = ContextPipeline([LostInMiddleReorder()])
        result = asyncio.run(pipeline.process([], "query"))
        assert result == []

    def test_steps_executed_in_order(self):
        class StepA:
            async def process(self, chunks, query):
                return [{**c, "text": c["text"] + "_A"} for c in chunks]

        class StepB:
            async def process(self, chunks, query):
                return [{**c, "text": c["text"] + "_B"} for c in chunks]

        pipeline = ContextPipeline([StepA(), StepB()])
        result = asyncio.run(pipeline.process([_chunk("x")], "q"))
        assert result[0]["text"] == "x_A_B"

    def test_step_exception_skipped(self):
        class FailingStep:
            async def process(self, chunks, query):
                raise RuntimeError("boom")

        class PassThrough:
            async def process(self, chunks, query):
                return chunks

        pipeline = ContextPipeline([FailingStep(), PassThrough()])
        chunks = [_chunk("a")]
        result = asyncio.run(pipeline.process(chunks, "q"))
        # FailingStep 异常被跳过，PassThrough 返回原始 chunks
        assert len(result) == 1
        assert result[0]["text"] == "a"

    def test_add_step_append(self):
        pipeline = ContextPipeline([])
        pipeline.add_step(LostInMiddleReorder())
        assert len(pipeline.steps) == 1

    def test_add_step_at_position(self):
        class StepA:
            async def process(self, chunks, query):
                return chunks
        class StepB:
            async def process(self, chunks, query):
                return chunks

        pipeline = ContextPipeline([StepA()])
        pipeline.add_step(StepB(), position=0)
        assert isinstance(pipeline.steps[0], StepB)

    def test_remove_step_by_class(self):
        pipeline = ContextPipeline([LostInMiddleReorder()])
        pipeline.remove_step(LostInMiddleReorder)
        assert len(pipeline.steps) == 0


# ── RelevanceFilter ──

class TestRelevanceFilter:
    def test_leq_min_chunks_skips_llm(self):
        llm = MockLLMClient("should_not_be_called")
        filt = RelevanceFilter(llm, min_chunks=3)
        chunks = [_chunk("a"), _chunk("b")]
        result = asyncio.run(filt.process(chunks, "query"))
        assert len(result) == 2
        assert len(llm.calls) == 0  # LLM 未被调用

    def test_filters_irrelevant_chunks(self):
        # LLM 判断 chunk 1 相关，chunk 2 不相关，chunk 3 相关
        llm_response = json.dumps([
            {"id": 1, "relevant": True},
            {"id": 2, "relevant": False},
            {"id": 3, "relevant": True},
        ])
        llm = MockLLMClient(llm_response)
        filt = RelevanceFilter(llm, min_chunks=1)
        chunks = [_chunk("relevant1"), _chunk("irrelevant"), _chunk("relevant2")]
        result = asyncio.run(filt.process(chunks, "query"))
        assert len(result) == 2
        assert result[0]["text"] == "relevant1"
        assert result[1]["text"] == "relevant2"

    def test_llm_failure_passes_through(self):
        llm = MockLLMClient("not valid json")
        filt = RelevanceFilter(llm, min_chunks=1)
        chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
        result = asyncio.run(filt.process(chunks, "query"))
        # LLM 解析失败 → 透传原 chunks
        assert len(result) == 3

    def test_fallback_keeps_min_chunks(self):
        # LLM 判断全部不相关，但应保留 min_chunks
        llm_response = json.dumps([
            {"id": 1, "relevant": False},
            {"id": 2, "relevant": False},
            {"id": 3, "relevant": False},
        ])
        llm = MockLLMClient(llm_response)
        filt = RelevanceFilter(llm, min_chunks=2)
        chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
        result = asyncio.run(filt.process(chunks, "query"))
        # 兜底保留前 min_chunks 个
        assert len(result) == 2


# ── SemanticCompressor ──

class TestSemanticCompressor:
    def test_short_text_not_compressed(self):
        llm = MockLLMClient("compressed")
        comp = SemanticCompressor(llm, min_chunk_len=200)
        chunks = [_chunk("短文本", 0.9)]  # 远短于 200
        result = asyncio.run(comp.process(chunks, "query"))
        assert len(result) == 1
        assert result[0]["text"] == "短文本"
        assert len(llm.calls) == 0  # LLM 未被调用

    def test_long_text_compressed(self):
        llm = MockLLMClient("这是压缩后的关键内容")
        comp = SemanticCompressor(llm, min_chunk_len=50)
        long_text = "这是一段很长的文本内容" * 10  # > 50 字符
        chunks = [_chunk(long_text, 0.9)]
        result = asyncio.run(comp.process(chunks, "query"))
        assert len(result) == 1
        assert result[0]["text"] == "这是压缩后的关键内容"
        assert result[0]["metadata"].get("compressed") is True

    def test_llm_failure_keeps_original(self):
        llm = MockLLMClient("")  # 空响应
        comp = SemanticCompressor(llm, min_chunk_len=10)
        long_text = "这是一段足够长的文本用于触发压缩" * 3
        chunks = [_chunk(long_text, 0.9)]
        result = asyncio.run(comp.process(chunks, "query"))
        assert len(result) == 1
        assert result[0]["text"] == long_text  # 保留原文

    def test_concurrent_compression(self):
        """多个长块并发压缩，结果数量不变。"""
        llm = MockLLMClient(["压缩1", "压缩2", "压缩3"])
        comp = SemanticCompressor(llm, min_chunk_len=10, max_concurrency=3)
        chunks = [
            _chunk("这是第一段足够长的文本内容" * 3, 0.9),
            _chunk("这是第二段足够长的文本内容" * 3, 0.8),
            _chunk("这是第三段足够长的文本内容" * 3, 0.7),
        ]
        result = asyncio.run(comp.process(chunks, "query"))
        assert len(result) == 3

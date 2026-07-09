"""精排重排模块测试 — src/retrieval/rerank.py。"""
import pytest
import asyncio
from src.interfaces.llm import ILLMClient, Message
from src.interfaces.vector_store import SearchResult
from src.retrieval.rerank import llm_rerank, _truncate_head_tail, RERANK_PROMPT


class MockLLMClient(ILLMClient):
    """返回预定义的 LLM 排序结果。"""
    def __init__(self, response: str | None = None):
        self._response = response

    async def chat(self, messages, temperature=0.7, max_tokens=2048) -> str:
        if self._response is not None:
            return self._response
        return '[{"id": 1, "score": 10}, {"id": 3, "score": 8}, {"id": 2, "score": 5}]'

    async def chat_stream(self, messages, temperature=0.7, max_tokens=2048):
        for token in []:
            yield token
        return


def _hit(text: str, score: float = 0.8, hid: str = "1", doc_id: str = "1") -> SearchResult:
    return SearchResult(id=hid, text=text, score=score, metadata={"doc_id": doc_id, "chunk_index": 0})


class TestTruncateHeadTail:
    """_truncate_head_tail 首尾截断。"""

    def test_short_text_unchanged(self):
        text = "短文本"
        assert _truncate_head_tail(text, max_chars=300) == text

    def test_long_text_truncated(self):
        text = "A" * 500
        result = _truncate_head_tail(text, max_chars=300)
        assert len(result) < 400  # 150 头 + "...\n...\n" + 150 尾
        assert result.startswith("A" * 150)
        assert result.endswith("A" * 150)

    def test_exact_boundary(self):
        text = "B" * 300
        result = _truncate_head_tail(text, max_chars=300)
        assert result == text  # 刚好等于阈值，不截断


class TestRerankBasic:
    """llm_rerank 基础功能。"""

    def test_few_candidates_no_rerank(self):
        """候选 ≤ top_k 时不触发重排，直接返回原列表。"""
        candidates = [_hit("A", 0.9), _hit("B", 0.8)]
        llm = MockLLMClient()
        result = asyncio.run(llm_rerank("test", candidates, llm, top_k=5))
        assert result == candidates

    def test_enough_candidates_triggers_rerank(self):
        candidates = [
            _hit(f"文档内容_{i}" * 20, score=0.9 - i * 0.05, hid=str(i))
            for i in range(8)
        ]
        llm = MockLLMClient()
        result = asyncio.run(llm_rerank("测试查询", candidates, llm, top_k=3))
        assert len(result) <= 3

    def test_llm_failure_graceful_degradation(self):
        """LLM 调用失败时降级返回原始 top_k。"""
        candidates = [_hit(f"doc_{i}" * 20, score=0.9 - i * 0.05, hid=str(i)) for i in range(10)]

        class FailingLLM(ILLMClient):
            async def chat(self, messages, temperature=0.7, max_tokens=2048):
                raise RuntimeError("API error")
            async def chat_stream(self, messages, temperature=0.7, max_tokens=2048):
                raise RuntimeError("API error")
                yield  # unreachable

        llm = FailingLLM()
        result = asyncio.run(llm_rerank("query", candidates, llm, top_k=5))
        assert len(result) == 5
        # 降级返回前5条
        for i in range(5):
            assert result[i].id == str(i)

    def test_score_fusion(self):
        """验证分数融合：final = α × LLM_score + (1-α) × vector_score。"""
        candidates = [_hit(f"内容_{i}" * 30, score=0.8, hid=str(i + 1)) for i in range(6)]
        # LLM 返回：id=1 score=10, id=2 score=5
        llm = MockLLMClient('[{"id": 1, "score": 10}, {"id": 2, "score": 5}]')
        result = asyncio.run(llm_rerank("查询", candidates, llm, top_k=2, fusion_alpha=0.7))

        assert len(result) == 2
        for r in result:
            assert "llm_score" in r.metadata
            assert "vector_score" in r.metadata


class TestRerankParse:
    """LLM 输出解析的各种情况。

    ⚠️ 重要：rerank 模块中 id_to_candidate = {i+1: c} (1-indexed)
    所以 LLM 返回的 id 必须是 [1, len(candidates)] 范围。
    """

    def test_plain_json(self):
        candidates = [_hit(f"c{i}" * 30, score=0.8, hid=str(i)) for i in range(8)]
        # id=1 对应 candidates[0], id=2 对应 candidates[1]
        llm = MockLLMClient('[{"id": 1, "score": 9}, {"id": 2, "score": 7}]')
        result = asyncio.run(llm_rerank("q", candidates, llm, top_k=2))
        assert len(result) == 2

    def test_code_fence_json(self):
        candidates = [_hit(f"c{i}" * 30, score=0.8, hid=str(i)) for i in range(8)]
        llm = MockLLMClient('```json\n[{"id": 1, "score": 10}, {"id": 2, "score": 8}]\n```')
        result = asyncio.run(llm_rerank("q", candidates, llm, top_k=2))
        assert len(result) == 2

    def test_json_with_extra_text(self):
        """JSON 被包裹在额外文字中，正则兜底提取。"""
        candidates = [_hit(f"c{i}" * 30, score=0.8, hid=str(i)) for i in range(8)]
        llm = MockLLMClient('根据分析，最相关的片段是 [{"id": 1, "score": 10}]，其他相关性较低。')
        result = asyncio.run(llm_rerank("q", candidates, llm, top_k=2))
        assert len(result) == 1

    def test_invalid_json_fallback(self):
        candidates = [_hit(f"c{i}" * 30, score=0.8, hid=str(i)) for i in range(8)]
        llm = MockLLMClient("这不是有效的JSON输出")
        result = asyncio.run(llm_rerank("q", candidates, llm, top_k=3))
        # 解析失败 → 降级返回原始 top_k
        assert len(result) == 3
        assert result[0].id == "0"

    def test_non_numeric_score_safe(self):
        """score 字段为非数字时的防御性处理。"""
        candidates = [_hit(f"c{i}" * 30, score=0.8, hid=str(i + 1)) for i in range(6)]
        llm = MockLLMClient('[{"id": 1, "score": "high"}, {"id": 2, "score": "medium"}]')
        result = asyncio.run(llm_rerank("q", candidates, llm, top_k=2))
        # 非数字 score → llm_score=0.0，不影响融合
        for r in result:
            assert r.score >= 0.0

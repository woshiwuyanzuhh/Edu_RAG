"""查询扩展器测试 — src/retrieval/query/expander.py。"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.interfaces.llm import ILLMClient, Message
from src.retrieval.query.expander import LLMQueryExpander, QUERY_EXPAND_PROMPT


class MockLLMClient(ILLMClient):
    def __init__(self, response: str = ""):
        self._response = response
        self._chat_calls: list[dict] = []

    async def chat(self, messages, temperature=0.7, max_tokens=2048) -> str:
        self._chat_calls.append({"messages": messages, "temperature": temperature})
        return self._response

    async def chat_stream(self, messages, temperature=0.7, max_tokens=2048):
        for token in ["test"]:
            yield token


class TestLLMQueryExpander:
    """LLMQueryExpander 核心功能 — 使用 asyncio.run() 模式。"""

    def _make_expander(self, response: str = "") -> LLMQueryExpander:
        return LLMQueryExpander(MockLLMClient(response))

    def test_expand_returns_list(self):
        """扩展器返回查询列表且始终包含原始问题。"""
        with patch.object(LLMQueryExpander, 'expand', wraps=None) as _:
            pass

        # 直接 mock cache_strategy 的 get/set
        with patch("src.retrieval.query.expander.cache_strategy") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=None)

            expander = self._make_expander(
                "机器学习的定义和基本概念\n机器学习核心原理\n机器学习应用场景\n机器学习算法分类"
            )
            result = asyncio.run(expander.expand("什么是机器学习", n=4))
            assert isinstance(result, list)
            assert "什么是机器学习" in result
            assert len(result) <= 4

    def test_result_strips_numbering(self):
        """编号前缀应被清理。"""
        with patch("src.retrieval.query.expander.cache_strategy") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=None)

            expander = self._make_expander(
                "1.机器学习的定义\n2.机器学习核心原理\n3.机器学习应用场景\n4.机器学习算法"
            )
            result = asyncio.run(expander.expand("什么是机器学习", n=4))
            for q in result:
                assert not q.startswith("1.")
                assert not q.startswith("2.")

    def test_duplicate_original_not_duplicated(self):
        """如果 LLM 已返回原始问题，不要重复插入。"""
        with patch("src.retrieval.query.expander.cache_strategy") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=None)

            expander = self._make_expander(
                "什么是机器学习\n机器学习核心原理\n机器学习应用场景\n机器学习算法分类"
            )
            result = asyncio.run(expander.expand("什么是机器学习", n=4))
            assert result.count("什么是机器学习") == 1

    def test_cache_hit_returns_cached(self):
        """缓存命中时直接返回缓存结果，不调 LLM。"""
        with patch("src.retrieval.query.expander.cache_strategy") as mock_cache:
            cached = ["查询A", "查询B", "查询C"]
            mock_cache.get = AsyncMock(return_value=cached)

            expander = self._make_expander("不应被调用")
            result = asyncio.run(expander.expand("任意问题", n=3))
            assert result == cached
            # LLM 不应被调用
            assert len(expander._llm._chat_calls) == 0

    def test_llm_failure_fallback_to_original(self):
        """LLM 调用失败时降级为仅返回原始问题。"""
        with patch("src.retrieval.query.expander.cache_strategy") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)

            class FailingLLM(ILLMClient):
                async def chat(self, messages, temperature=0.7, max_tokens=2048):
                    raise RuntimeError("API 不可用")
                async def chat_stream(self, messages, temperature=0.7, max_tokens=2048):
                    raise RuntimeError("API 不可用")
                    yield

            expander = LLMQueryExpander(FailingLLM())
            result = asyncio.run(expander.expand("什么是RAG", n=4))
            assert result == ["什么是RAG"]

    def test_empty_llm_response_handled(self):
        """LLM 返回空字符串时仍返回原始问题。"""
        with patch("src.retrieval.query.expander.cache_strategy") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=None)

            expander = self._make_expander("")
            result = asyncio.run(expander.expand("测试问题", n=4))
            assert "测试问题" in result

    def test_truncate_to_n(self):
        """结果应被截断到 n 个。"""
        with patch("src.retrieval.query.expander.cache_strategy") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=None)

            expander = self._make_expander("Q1\nQ2\nQ3\nQ4\nQ5\nQ6")
            result = asyncio.run(expander.expand("test", n=3))
            assert len(result) == 3

    def test_prompt_contains_question(self):
        """验证 prompt 中包含用户问题。"""
        with patch("src.retrieval.query.expander.cache_strategy") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=None)

            expander = self._make_expander("查询角度1\n查询角度2")
            asyncio.run(expander.expand("什么是深度学习", n=3))
            # 检查 LLM 被调用了
            llm = expander._llm
            assert len(llm._chat_calls) == 1
            sent_messages = llm._chat_calls[0]["messages"]
            prompt_text = sent_messages[0].content
            assert "什么是深度学习" in prompt_text


class TestExpandPrompt:
    """验证 prompt 模板。"""

    def test_prompt_has_placeholder(self):
        assert "{question}" in QUERY_EXPAND_PROMPT

    def test_prompt_mentions_output_format(self):
        assert "每行一个查询" in QUERY_EXPAND_PROMPT
        assert "不要编号" in QUERY_EXPAND_PROMPT

"""问答引擎测试 — src/generation/qa_engine.py。"""
import pytest
import asyncio
from src.interfaces.llm import ILLMClient, Message
from src.interfaces.vector_store import SearchResult
from src.retrieval.service import RetrievalService
from src.generation.qa_engine import qa_non_stream, _build_messages


class MockLLMClient(ILLMClient):
    def __init__(self, response: str = "这是一个测试回答。"):
        self._response = response

    async def chat(self, messages, temperature=0.7, max_tokens=2048) -> str:
        return self._response

    async def chat_stream(self, messages, temperature=0.7, max_tokens=2048):
        for token in ["这是", "测试", "回答"]:
            yield token


class MockEmbedder:
    async def embed(self, texts):
        return [[0.1] * 1024 for _ in texts]
    @property
    def dimension(self):
        return 1024


class MockVectorStore:
    def __init__(self, hits):
        self._hits = hits
    async def connect(self): pass
    async def disconnect(self): pass
    async def insert(self, items): pass
    async def search(self, query, top_k=5, filter_expr=None): return self._hits[:top_k]
    async def delete_by_ids(self, ids): pass
    async def delete_by_filter(self, filter_expr): pass
    async def count(self): return len(self._hits)


@pytest.fixture
def svc_no_hits():
    return RetrievalService(embedder=MockEmbedder(), vector_store=MockVectorStore([]))


@pytest.fixture
def svc_with_hits():
    hits = [SearchResult(id="1", text="RAG结合了检索和生成", score=0.9, metadata={"doc_id": "1"})]
    return RetrievalService(embedder=MockEmbedder(), vector_store=MockVectorStore(hits))


class TestQaNonStream:
    def test_no_hits_returns_fallback(self, svc_no_hits):
        llm = MockLLMClient()
        result = asyncio.run(qa_non_stream("test", llm, svc_no_hits, knowledge_base_id=1, use_rerank=False))
        assert "暂无相关内容" in result["answer"]
        assert result["sources"] == []

    def test_with_hits_returns_answer(self, svc_with_hits):
        llm = MockLLMClient("RAG的答案是...")
        result = asyncio.run(qa_non_stream("什么是RAG", llm, svc_with_hits, knowledge_base_id=1, use_rerank=False))
        assert "RAG的答案是" in result["answer"]
        assert len(result["sources"]) > 0

    def test_history_injected(self, svc_with_hits):
        llm = MockLLMClient()
        history = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
        result = asyncio.run(qa_non_stream("什么是RAG", llm, svc_with_hits,
                                           knowledge_base_id=1, use_rerank=False, history=history))
        assert "测试回答" in result["answer"]


class TestBuildMessages:
    def test_no_history(self):
        msgs = _build_messages("上下文内容", "什么是RAG", None)
        assert msgs[0].role == "system"
        assert msgs[-1].role == "user"
        assert "上下文内容" in msgs[-1].content
        assert "什么是RAG" in msgs[-1].content

    def test_with_history(self):
        history = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
        msgs = _build_messages("上下文", "问题", history)
        assert len(msgs) == 4  # system + 2 history + current
        assert msgs[1].role == "user" and msgs[1].content == "你好"
        assert msgs[2].role == "assistant" and msgs[2].content == "你好！"

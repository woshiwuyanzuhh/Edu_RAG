"""检索服务测试 — src/retrieval/service.py。"""
import pytest
import asyncio
from src.interfaces.embedder import IEmbedder
from src.interfaces.vector_store import IVectorStore, SearchResult
from src.retrieval.service import RetrievalService


class MockEmbedder(IEmbedder):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]

    @property
    def dimension(self) -> int:
        return 1024


class MockVectorStore(IVectorStore):
    def __init__(self, hits: list[SearchResult] | None = None):
        self._hits = hits or []

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def insert(self, items) -> None:
        pass

    async def search(self, query, top_k=5, filter_expr=None) -> list[SearchResult]:
        return self._hits[:top_k]

    async def delete_by_ids(self, ids) -> None:
        pass

    async def delete_by_filter(self, filter_expr) -> None:
        pass

    async def count(self) -> int:
        return len(self._hits)


@pytest.fixture
def svc():
    return RetrievalService(embedder=MockEmbedder(), vector_store=MockVectorStore())


@pytest.fixture
def svc_with_hits():
    hits = [
        SearchResult(id="1", text="RAG是检索增强生成技术", score=0.9, metadata={"doc_id": "1"}),
        SearchResult(id="2", text="深度学习使用神经网络", score=0.7, metadata={"doc_id": "2"}),
    ]
    return RetrievalService(embedder=MockEmbedder(), vector_store=MockVectorStore(hits))


class TestRetrieve:
    def test_retrieve_returns_list(self, svc_with_hits):
        result = asyncio.run(svc_with_hits.retrieve("什么是RAG", knowledge_base_id=1, use_rerank=False))
        assert isinstance(result, list)
        assert all(isinstance(h, SearchResult) for h in result)

    def test_retrieve_empty_store(self, svc):
        result = asyncio.run(svc.retrieve("任意查询", use_rerank=False))
        assert result == []

    def test_retrieve_with_context(self, svc_with_hits):
        result = asyncio.run(svc_with_hits.retrieve_with_context("什么是RAG"))
        assert "hits" in result
        assert "context" in result
        assert isinstance(result["context"], str)
        assert len(result["context"]) > 0

    def test_retrieve_with_context_empty(self, svc):
        result = asyncio.run(svc.retrieve_with_context("任意查询"))
        assert result["hits"] == []
        assert result["context"] == ""

    def test_build_context_for_exam(self, svc_with_hits):
        result = asyncio.run(svc_with_hits.build_context_for_exam(knowledge_base_id=1))
        assert isinstance(result, str)
        assert "【片段" in result

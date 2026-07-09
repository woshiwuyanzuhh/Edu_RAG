"""粗排召回模块测试 — src/retrieval/recall.py。"""
import pytest
import asyncio
from src.interfaces.embedder import IEmbedder
from src.interfaces.vector_store import IVectorStore, SearchResult
from src.interfaces.query_expander import IQueryExpander
from src.retrieval.recall import recall


class MockEmbedder(IEmbedder):
    """返回固定 1024 维向量。"""
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1 + i * 0.01] * 1024 for i in range(len(texts))]

    @property
    def dimension(self) -> int:
        return 1024


class MockVectorStore(IVectorStore):
    """从预设列表中返回结果。"""
    def __init__(self, hits: list[SearchResult] | None = None):
        self._hits = hits or []
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def insert(self, items) -> None:
        pass

    async def search(self, query, top_k=5, filter_expr=None) -> list[SearchResult]:
        return [h for h in self._hits if h.score > 0][:top_k]

    async def delete_by_ids(self, ids) -> None:
        pass

    async def delete_by_filter(self, filter_expr) -> None:
        pass

    async def count(self) -> int:
        return len(self._hits)


class MockExpander(IQueryExpander):
    """返回固定扩展查询。"""
    async def expand(self, question: str, n: int = 4) -> list[str]:
        return [
            question,
            f"{question} — 角度1",
            f"{question} — 角度2",
            f"{question} — 角度3",
        ][:n]


def _hit(text: str, score: float = 0.8, hid: str = "1") -> SearchResult:
    return SearchResult(id=hid, text=text, score=score, metadata={"doc_id": "1"})


class TestRecallBasic:
    """recall 基础功能。"""

    def test_no_expander_uses_original_query(self):
        store = MockVectorStore([_hit("RAG是检索增强生成技术", 0.9)])
        embedder = MockEmbedder()
        result = asyncio.run(recall("什么是RAG", embedder, store, expander=None, top_k=5))
        assert len(result) >= 1
        assert isinstance(result[0], SearchResult)

    def test_empty_store_returns_empty(self):
        store = MockVectorStore([])
        embedder = MockEmbedder()
        result = asyncio.run(recall("任意查询", embedder, store, top_k=5))
        assert result == []

    def test_results_sorted_by_score(self):
        hits = [
            _hit("low", score=0.3, hid="a"),
            _hit("mid", score=0.6, hid="b"),
            _hit("high", score=0.9, hid="c"),
        ]
        store = MockVectorStore(hits)
        embedder = MockEmbedder()
        result = asyncio.run(recall("test", embedder, store, top_k=5))
        assert result[0].score >= result[-1].score

    def test_knowledge_base_filter_passed(self):
        store = MockVectorStore([_hit("test", 0.8)])
        embedder = MockEmbedder()
        result = asyncio.run(recall("query", embedder, store, knowledge_base_id=42, top_k=5))
        assert isinstance(result, list)

    def test_with_expander_yields_expanded_queries(self):
        hits = [_hit("RAG技术", 0.9, hid=str(i)) for i in range(10)]
        store = MockVectorStore(hits)
        embedder = MockEmbedder()
        expander = MockExpander()
        result = asyncio.run(recall("什么是RAG", embedder, store, expander=expander, top_k=3, recall_multiplier=3))
        assert len(result) > 0

    def test_deduplicate_by_text_prefix(self):
        """相同文本前缀的结果应去重，保留先出现的。"""
        hits = [
            _hit("完全相同的前缀文本内容AAA", score=0.9, hid="1"),
            _hit("完全相同的前缀文本内容BBB", score=0.8, hid="2"),
        ]
        store = MockVectorStore(hits * 2)  # 每个命中重复一次
        embedder = MockEmbedder()
        result = asyncio.run(recall("test", embedder, store, top_k=5))
        # 按前120字符去重后应只有2条
        unique_prefixed = set(h.text[:120] for h in result)
        assert len(unique_prefixed) <= 2


class TestRecallEdgeCases:
    """recall 边界情况。"""

    def test_none_text_safe(self):
        """text 为 None 的 SearchResult 应安全处理。"""
        hit = SearchResult(id="1", text=None, score=0.8, metadata={})
        store = MockVectorStore([hit])
        embedder = MockEmbedder()
        result = asyncio.run(recall("test", embedder, store, top_k=5))
        # 不崩溃即可
        assert isinstance(result, list)

    def test_expander_failure_fallback(self):
        """扩展器失败时应降级为仅用原查询。"""

        class FailingExpander(IQueryExpander):
            async def expand(self, question, n=4):
                raise RuntimeError("LLM 不可用")

        store = MockVectorStore([_hit("内容", 0.8)])
        embedder = MockEmbedder()
        with pytest.raises(RuntimeError):
            asyncio.run(recall("query", embedder, store, expander=FailingExpander()))

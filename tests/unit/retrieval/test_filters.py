"""检索过滤器测试 — src/retrieval/filters.py。"""
import pytest
from src.interfaces.vector_store import SearchResult
from src.retrieval.filters import (
    filter_by_score, deduplicate_by_text, lost_in_middle_reorder, build_context,
)


def _hit(text: str, score: float = 0.8, doc_id: str = "1") -> SearchResult:
    return SearchResult(id="1", text=text, score=score, metadata={"doc_id": doc_id, "chunk_index": 0})


class TestFilterByScore:
    def test_below_threshold_filtered(self):
        hits = [_hit("good", 0.8), _hit("bad", 0.1)]
        result = filter_by_score(hits, min_score=0.3)
        assert len(result) == 1

    def test_custom_threshold(self):
        hits = [_hit("a", 0.5), _hit("b", 0.6)]
        result = filter_by_score(hits, min_score=0.7)
        assert len(result) == 0


class TestDeduplicateByText:
    def test_duplicate_removed(self):
        hits = [_hit("same text prefix here"), _hit("same text prefix different suffix")]
        result = deduplicate_by_text(hits, prefix_len=15)
        assert len(result) == 1

    def test_unique_texts_preserved(self):
        hits = [_hit("completely different 1"), _hit("completely different 2")]
        result = deduplicate_by_text(hits)
        assert len(result) == 2

    def test_none_text_safe(self):
        hits = [SearchResult(id="1", text=None, score=0.8, metadata={})]
        result = deduplicate_by_text(hits)
        assert len(result) == 1


class TestLostInMiddleReorder:
    def test_few_hits_unchanged(self):
        hits = [_hit("a", 0.9), _hit("b", 0.8)]
        result = lost_in_middle_reorder(hits)
        assert result == hits

    def test_reorder_puts_best_first(self):
        hits = [_hit("best", 0.9), _hit("second", 0.85), _hit("third", 0.8), _hit("fourth", 0.7)]
        result = lost_in_middle_reorder(hits)
        assert result[0].score == 0.9  # best first
        assert result[-1].score == 0.85  # second_best last


class TestBuildContext:
    def test_empty_hits(self):
        assert build_context([]) == ""

    def test_below_threshold_empty(self):
        hits = [_hit("x", 0.1)]
        assert build_context(hits, min_score=0.3) == ""

    def test_format_includes_fragment_markers(self):
        hits = [_hit("这是测试内容这是测试内容这是测试内容这是测试内容" * 2, score=0.8)]
        result = build_context(hits, reorder=False)
        assert "【片段1】" in result
        assert "这是测试内容" in result

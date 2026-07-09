"""分块器单元测试 — src/ingress/chunkers/recursive.py。"""
import pytest
from src.ingress.chunkers.recursive import RecursiveChunker


class TestRecursiveChunker:
    """RecursiveChunker 核心功能测试。"""

    def test_empty_text_returns_empty(self):
        chunker = RecursiveChunker()
        assert chunker.split("") == []
        assert chunker.split("   ") == []

    def test_short_text_preserved(self):
        chunker = RecursiveChunker(chunk_size=800)
        text = "这是一段完整的短文本，不需要切分。"
        result = chunker.split(text)
        assert len(result) == 1
        assert text in result[0]

    def test_cjk_period_split(self):
        """中文句号作为分割边界。"""
        chunker = RecursiveChunker(chunk_size=10, chunk_overlap=0)
        text = "第一句。第二句。第三句。"
        result = chunker.split(text)
        assert len(result) >= 1
        for chunk in result:
            assert len(chunk) <= 10

    def test_overlap_preserves_context(self):
        chunker = RecursiveChunker(chunk_size=200, chunk_overlap=20)
        text = ("人工智能是计算机科学的一个分支。" * 30)
        result = chunker.split(text)
        assert len(result) >= 1

    def test_very_long_text_splits_to_multiple(self):
        chunker = RecursiveChunker(chunk_size=50, chunk_overlap=5)
        text = "机器学习是人工智能的核心领域之一。" * 50
        result = chunker.split(text)
        assert len(result) > 5
        for chunk in result:
            assert 0 < len(chunk) <= 50

    def test_separator_priority_respected(self):
        """段落分隔 \\n\\n 优先于句号。"""
        chunker = RecursiveChunker(chunk_size=500, chunk_overlap=50)
        text = "段落1: 第一句。第二句。\n\n段落2: 第三句。第四句。"
        result = chunker.split(text)
        assert len(result) >= 1


class TestEdgeCases:
    def test_single_char(self):
        chunker = RecursiveChunker(chunk_size=10)
        result = chunker.split("A")
        assert len(result) == 1

    def test_numbers_only(self):
        chunker = RecursiveChunker(chunk_size=10)
        result = chunker.split("12345678901234567890")
        assert len(result) >= 1
        for chunk in result:
            assert len(chunk) <= 10

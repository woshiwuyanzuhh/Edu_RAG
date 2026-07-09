"""清洗器单元测试 — src/ingress/cleaners/。"""
import pytest
from src.ingress.cleaners.base import BaseCleaner
from src.ingress.cleaners.education import EducationCleaner


class TestBaseCleaner:
    def test_control_chars_removed(self):
        cleaner = BaseCleaner()
        text = "hello\x00\x1fworld"
        result = cleaner.clean(text)
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_urls_removed(self):
        cleaner = BaseCleaner()
        text = "访问 https://example.com/page 了解更多"
        result = cleaner.clean(text)
        assert "https://example.com/page" not in result
        assert "了解更多" in result

    def test_html_tags_removed(self):
        cleaner = BaseCleaner()
        text = "<p>这是内容</p>"
        result = cleaner.clean(text)
        assert "<p>" not in result
        assert "这是内容" in result

    def test_markdown_links_cleaned(self):
        cleaner = BaseCleaner()
        text = "点击[链接](http://example.com)查看"
        result = cleaner.clean(text)
        # Markdown 链接被清洗：保留文本"链接"，去除 URL
        assert "http://example.com" not in result
        assert "链接" in result

    def test_linebreaks_normalized(self):
        cleaner = BaseCleaner()
        text = "第一行\n\n\n\n第二行"
        result = cleaner.clean(text)
        assert "\n\n\n\n" not in result


class TestFilterChunks:
    def test_short_chunk_filtered(self):
        cleaner = BaseCleaner()
        chunks = ["ab", "这是有效内容这是有效内容这是有效内容", "x"]
        result = cleaner.filter_chunks(chunks)
        assert len(result) == 1

    def test_duplicates_removed(self):
        cleaner = BaseCleaner()
        content = "这是一个有足够长度的测试文本块用于去重测试。"
        chunks = [content, content, content + "微小变化"]
        result = cleaner.filter_chunks(chunks)
        # 高相似度的应该被合并
        assert len(result) <= 2


class TestEducationCleaner:
    def test_page_numbers_removed(self):
        cleaner = EducationCleaner()
        text = "第1页\n内容正文\n- 2 -"
        result = cleaner.clean(text)
        assert "第1页" not in result

    def test_watermark_removed(self):
        cleaner = EducationCleaner()
        text = "内部资料\n正文内容\n请勿外传"
        result = cleaner.clean(text)
        assert "内部资料" not in result
        assert "请勿外传" not in result
        assert "正文内容" in result

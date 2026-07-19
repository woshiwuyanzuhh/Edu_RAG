"""
通用文本清洗器 — 所有文档类型的基础清洗。

清洗步骤：
    1. 移除控制字符（保留 \\n \\t）
    2. 移除零宽字符和 BOM
    3. 全角字母/数字 → 半角（保留中文标点）
    4. 移除 URL 和 Email
    5. 移除 HTML 标签和实体
    6. Markdown 链接/图片 → 纯文本
    7. 统一换行符
    8. 统一空白字符

切分后过滤：
    - 长度 < 15 字符 → 丢弃
    - CJK+Latin 占比 < 20% → 丢弃
    - Jaccard ≥ 0.92 → 去重

辅助工具（供子类复用）：
    - _filter_lines: 按一组断言逐行过滤，命中任一断言的行被丢弃
"""

import re
from collections.abc import Callable

from src.interfaces.cleaner import ICleaner


class BaseCleaner(ICleaner):
    """通用文本清洗器。"""

    # ── 清洗 ──

    def clean(self, text: str) -> str:
        text = self._strip_control_chars(text)
        text = self._strip_zero_width(text)
        text = self._normalize_width(text)
        text = self._remove_urls(text)
        text = self._remove_html_tags(text)
        text = self._clean_markdown_links(text)
        text = self._normalize_linebreaks(text)
        text = self._normalize_whitespace(text)
        return text

    # ── 子类复用工具 ──

    @staticmethod
    def _filter_lines(text: str, predicates: list[Callable[[str], bool]]) -> str:
        """按断言逐行过滤。

        Args:
            text: 待过滤文本
            predicates: 断言列表；某行命中任一断言（返回 True）即被丢弃

        Returns:
            过滤后的文本（保留原始换行结构）
        """
        if not predicates:
            return text
        kept: list[str] = []
        for line in text.split("\n"):
            stripped = line.strip()
            if any(p(stripped) for p in predicates):
                continue
            kept.append(line)
        return "\n".join(kept)

    @staticmethod
    def _strip_control_chars(text: str) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    @staticmethod
    def _strip_zero_width(text: str) -> str:
        return re.sub(r"[​‌‍‎‏﻿]", "", text)

    @staticmethod
    def _normalize_width(text: str) -> str:
        result = []
        for ch in text:
            code = ord(ch)
            if 0xFF21 <= code <= 0xFF3A:
                result.append(chr(code - 0xFF21 + ord("A")))
            elif 0xFF41 <= code <= 0xFF5A:
                result.append(chr(code - 0xFF41 + ord("a")))
            elif 0xFF10 <= code <= 0xFF19:
                result.append(chr(code - 0xFF10 + ord("0")))
            elif code == 0x3000:
                result.append(" ")
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _remove_urls(text: str) -> str:
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "", text)
        return text

    @staticmethod
    def _remove_html_tags(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        entities = {
            "&nbsp;": " ",
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&apos;": "'",
            "&#160;": " ",
        }
        for ent, repl in entities.items():
            text = text.replace(ent, repl)
        return text

    @staticmethod
    def _clean_markdown_links(text: str) -> str:
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", text)
        return text

    @staticmethod
    def _normalize_linebreaks(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return re.sub(r"\n{3,}", "\n\n", text)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        text = text.replace("\t", " ")
        return re.sub(r" {2,}", " ", text)

    # ── 切分后过滤 ──

    def filter_chunks(self, chunks: list[str]) -> list[str]:
        chunks = [c for c in chunks if self._is_valid_chunk(c)]
        return self._deduplicate(chunks)

    @staticmethod
    def _char_ratio(text: str, pattern: str) -> float:
        total = len(text)
        if total == 0:
            return 0.0
        return len(re.findall(pattern, text)) / total

    @classmethod
    def _is_valid_chunk(cls, chunk: str) -> bool:
        text = chunk.strip()
        if len(text) < 15:
            return False
        cjk = cls._char_ratio(text, r"[一-鿿]")
        latin = cls._char_ratio(text, r"[a-zA-Z]")
        content_ratio = cjk + latin
        if content_ratio == 0:
            return False
        if content_ratio < 0.2:
            return False
        return True

    @staticmethod
    def _deduplicate(chunks: list[str], threshold: float = 0.92) -> list[str]:
        if len(chunks) <= 1:
            return chunks
        kept = [chunks[0]]
        for c in chunks[1:]:
            if all(BaseCleaner._jaccard(c, k) < threshold for k in kept):
                kept.append(c)
        return kept

    @staticmethod
    def _jaccard(a: str, b: str, n: int = 2) -> float:
        def _grams(s):
            return {s[i : i + n] for i in range(len(s) - n + 1)}

        sa, sb = _grams(a), _grams(b)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

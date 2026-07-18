"""文学作品清洗器 — 过滤 OCR 噪声、章节编号噪声，保留对话格式。

适用场景：小说、散文、诗歌、剧本。
保留：对话引号、段落结构、文学性表达。
特殊处理：
    - 不过滤短行（诗歌、对话可能很短）
    - 保留引号内的内容
"""
import re

from src.ingress.cleaners.base import BaseCleaner


class LiteratureCleaner(BaseCleaner):
    """文学作品专用清洗器。

    注意：文学作品的 filter_chunks 阈值更宽松，
    允许短句通过（诗歌、对话）。
    """

    def clean(self, text: str) -> str:
        text = super().clean(text)
        text = self._filter_lines(text, [
            self._is_ocr_garbage,
            self._is_chapter_noise,
        ])
        return text

    @staticmethod
    def _is_ocr_garbage(line: str) -> bool:
        """OCR 噪声行：全是乱码字符或符号堆砌。"""
        if not line:
            return False
        # 非文字占比过高
        cjk = len(re.findall(r"[一-鿿]", line))
        latin = len(re.findall(r"[a-zA-Z]", line))
        total = len(line)
        if total == 0:
            return False
        # 非文字字符（标点、符号、控制符）占比 > 70%
        non_text = total - cjk - latin
        return (non_text / total) > 0.7 and total > 3

    @staticmethod
    def _is_chapter_noise(line: str) -> bool:
        """章节编号噪声行：纯 `第X章` / `Chapter X` 无标题。"""
        if len(line) > 30:
            return False
        patterns = [
            r"^第\s*[一二三四五六七八九十百千\d]+\s*[章节回卷]\s*$",
            r"^Chapter\s+\d+\s*$",
            r"^[\-—=]{5,}\s*$",  # 分隔线
        ]
        return any(re.match(p, line, re.IGNORECASE) for p in patterns)

    def filter_chunks(self, chunks: list[str]) -> list[str]:
        """文学作品允许短句通过（诗歌、对话）。

        阈值从 15 降到 8，字符占比从 0.2 降到 0.1。
        """
        chunks = [c for c in chunks if self._is_valid_literary_chunk(c)]
        return self._deduplicate(chunks)

    @classmethod
    def _is_valid_literary_chunk(cls, chunk: str) -> bool:
        text = chunk.strip()
        if len(text) < 8:  # 宽松阈值
            return False
        cjk = cls._char_ratio(text, r"[一-鿿]")
        latin = cls._char_ratio(text, r"[a-zA-Z]")
        content_ratio = cjk + latin
        if content_ratio == 0:
            return False
        if content_ratio < 0.1:  # 宽松阈值
            return False
        return True

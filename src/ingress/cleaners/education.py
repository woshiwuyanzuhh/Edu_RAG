"""教育文档清洗器 — 在通用清洗基础上增加页码/水印/参考文献过滤。"""

import re

from src.ingress.cleaners.base import BaseCleaner


class EducationCleaner(BaseCleaner):
    """教育文档专用清洗器。"""

    def clean(self, text: str) -> str:
        text = super().clean(text)
        text = self._clean_education(text)
        return text

    @staticmethod
    def _clean_education(text: str) -> str:
        lines = text.split("\n")
        kept = []
        for line in lines:
            stripped = line.strip()
            if EducationCleaner._is_page_number(stripped):
                continue
            if EducationCleaner._is_watermark(stripped):
                continue
            if EducationCleaner._is_reference_line(stripped):
                continue
            kept.append(line)
        return "\n".join(kept)

    @staticmethod
    def _is_page_number(line: str) -> bool:
        patterns = [
            r"^第?\s*\d+\s*[页Pp](\s*[共总]\s*\d+\s*[页Pp])?$",
            r"^[-—]*\s*\d+\s*[-—]*$",
            r"^\d+\s*/\s*\d+$",
        ]
        return any(re.match(p, line) for p in patterns)

    @staticmethod
    def _is_watermark(line: str) -> bool:
        keywords = [
            "内部资料",
            "请勿外传",
            "机密",
            "绝密",
            "Confidential",
            "仅供内部使用",
            "版权所有",
            "翻印必究",
            "不得转载",
        ]
        return any(kw in line for kw in keywords)

    @staticmethod
    def _is_reference_line(line: str) -> bool:
        return bool(re.match(r"^\s*\[\d+\]\s+.+\b\d{4}\b", line))

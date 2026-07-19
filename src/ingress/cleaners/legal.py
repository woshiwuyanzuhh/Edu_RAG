"""法律法规文档清洗器 — 过滤页眉页脚、司法解释水印、文书编号噪声。

适用场景：法条、判例、合同、法律意见书。
保留：法条编号（第X条）、法引用、条款结构。
"""

import re

from src.ingress.cleaners.base import BaseCleaner


class LegalCleaner(BaseCleaner):
    """法律法规文档专用清洗器。"""

    def clean(self, text: str) -> str:
        text = super().clean(text)
        return self._filter_lines(
            text,
            [
                self._is_judicial_watermark,
                self._is_page_header_footer,
                self._is_document_number,
            ],
        )

    @staticmethod
    def _is_judicial_watermark(line: str) -> bool:
        """司法文书水印/密级行。"""
        keywords = [
            "机密",
            "秘密",
            "内部使用",
            "仅供参阅",
        ]
        if len(line) > 30:
            return False
        # 仅匹配单独出现的法院/检察院落款（行末为"法院"/"检察院"的短行），
        # 避免误杀正文中提及法院的句子（如"由人民法院管辖"）。
        is_court_signature = bool(re.search(r"(人民法院|人民检察院|高等法院)\s*$", line))
        return any(kw in line for kw in keywords) or is_court_signature

    @staticmethod
    def _is_page_header_footer(line: str) -> bool:
        """页眉页脚：含页码或文档标题重复行。"""
        patterns = [
            r"^第\s*\d+\s*页\s*(共\s*\d+\s*页)?$",
            r"^\d+\s*/\s*\d+$",
            r"^[-—·•]{3,}\s*\d+\s*[-—·•]{3,}$",
        ]
        return any(re.match(p, line) for p in patterns)

    @staticmethod
    def _is_document_number(line: str) -> bool:
        """文书编号行：`(2023)京01民初123号` 等，单独成行时过滤。"""
        if len(line) > 40:
            return False
        return bool(re.match(r"^\(?\s*\d{4}\s*\)?[\u4e00-\u9fff]\d{2,}[\u4e00-\u9fff]+字第?\d+号$", line))

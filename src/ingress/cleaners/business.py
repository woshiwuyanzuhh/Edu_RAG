"""商业管理文档清洗器 — 过滤 PPT 页码、机密水印、页眉页脚。

适用场景：商业报告、管理文档、PPT 导出文本、会议纪要。
保留：数据图表描述、分析结论、管理术语。
"""
import re

from src.ingress.cleaners.base import BaseCleaner


class BusinessCleaner(BaseCleaner):
    """商业管理文档专用清洗器。"""

    def clean(self, text: str) -> str:
        text = super().clean(text)
        return self._filter_lines(text, [
            self._is_ppt_page_number,
            self._is_confidential_watermark,
            self._is_slide_footer,
            self._is_corporate_boilerplate,
        ])

    @staticmethod
    def _is_ppt_page_number(line: str) -> bool:
        """PPT 页码：`1 / 10` / `Slide 1` 等。"""
        if len(line) > 25:
            return False
        patterns = [
            r"^\d+\s*/\s*\d+\s*$",
            r"^slide\s+\d+$",
            r"^第\s*\d+\s*页\s*$",
        ]
        return any(re.match(p, line, re.IGNORECASE) for p in patterns)

    @staticmethod
    def _is_confidential_watermark(line: str) -> bool:
        """机密/内部水印行。"""
        if len(line) > 30:
            return False
        keywords = [
            "机密", "绝密", "内部使用", "内部资料",
            "Confidential", "Proprietary",
            "商业秘密", "不得外传",
        ]
        return any(kw in line for kw in keywords)

    @staticmethod
    def _is_slide_footer(line: str) -> bool:
        """PPT 页脚：公司名 + 页码 的短行。"""
        if len(line) > 40:
            return False
        # 公司名后跟页码
        return bool(re.match(r"^[\u4e00-\u9fff\w]+(\s*[\(（].+[\)）])?\s*[-—·]?\s*\d+\s*$", line))

    @staticmethod
    def _is_corporate_boilerplate(line: str) -> bool:
        """公司模板套话行。"""
        if len(line) > 35:
            return False
        patterns = [
            r"本报告?由.+公司出品",
            r"关注.+公众号",
            r"扫码.*(?:关注|加入|更多)",
            r"官网\s*[:：]",
        ]
        return any(re.search(p, line) for p in patterns)

"""新闻资讯清洗器 — 过滤版权声明、记者署名、编辑信息、来源行。

适用场景：新闻报道、资讯文章、媒体稿件。
保留：新闻正文、引用、时间地点信息。
"""

import re

from src.ingress.cleaners.base import BaseCleaner


class NewsCleaner(BaseCleaner):
    """新闻资讯文档专用清洗器。"""

    def clean(self, text: str) -> str:
        text = super().clean(text)
        return self._filter_lines(
            text,
            [
                self._is_copyright_notice,
                self._is_reporter_byline,
                self._is_editor_info,
                self._is_source_line,
            ],
        )

    @staticmethod
    def _is_copyright_notice(line: str) -> bool:
        """版权声明行。"""
        keywords = [
            "版权所有",
            "未经授权",
            "不得转载",
            "违者必究",
            "转自",
            "摘自",
        ]
        # 来源行：支持中英文冒号，且要求在行首附近出现
        is_source = bool(re.match(r"^.{0,6}来源\s*[:：]", line))
        return (any(kw in line for kw in keywords) or is_source) and len(line) < 50

    @staticmethod
    def _is_reporter_byline(line: str) -> bool:
        """记者署名行。"""
        patterns = [
            r"(?:记者|通讯员|报道员)\s*[:：]?\s*[\u4e00-\u9fff]{2,4}",
            r"[\u4e00-\u9fff]{2,4}\s*(?:记者|通讯员|报道员)",
            r"摄影\s*[:：]\s*[\u4e00-\u9fff]{2,4}",
        ]
        return any(re.search(p, line) for p in patterns) and len(line) < 30

    @staticmethod
    def _is_editor_info(line: str) -> bool:
        """编辑/责编信息行。"""
        patterns = [
            r"编辑\s*[:：]\s*\S+",
            r"责编\s*[:：]\s*\S+",
            r"校对\s*[:：]\s*\S+",
            r"主编\s*[:：]\s*\S+",
        ]
        return any(re.search(p, line) for p in patterns) and len(line) < 30

    @staticmethod
    def _is_source_line(line: str) -> bool:
        """来源行：`XXX网讯` / `XXX报道` 单独成行。"""
        if len(line) > 20:
            return False
        return bool(re.match(r"^[\u4e00-\u9fff]{2,8}(网|日报|晚报|晨报|新闻|通讯社|周刊|电视台|广播)", line))

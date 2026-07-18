"""技术文档清洗器 — 过滤代码行号、shell 提示符、TODO/FIXME 注释行。

适用场景：IT/编程教程、API 文档、软件手册、技术博客。
保留：代码块内容、技术术语、配置示例。
"""
import re

from src.ingress.cleaners.base import BaseCleaner


class TechCleaner(BaseCleaner):
    """技术文档专用清洗器。"""

    def clean(self, text: str) -> str:
        text = super().clean(text)
        return self._filter_lines(text, [
            self._is_shell_prompt,
            self._is_line_number_prefix,
            self._is_todo_comment,
            self._is_diff_marker_only,
        ])

    @staticmethod
    def _is_shell_prompt(line: str) -> bool:
        """shell 提示符行：`$ command` / `> command` / `user@host:~$ command`。

        注意：`user@host:~#` 中的 `#` 是 root shell 提示符（非注释），
        会一并被匹配。纯 `# 注释` 行不在本规则处理范围。
        """
        # `user@host:~$` 或 `user@host:~#`（root）形式
        if re.match(r"^[\w.-]+@[\w.-]+:.+[$#]\s", line):
            return True
        # `$ ` 或 `> ` 开头且行很短（避免误杀正文中的 $ 符号）
        if re.match(r"^[$>]\s+.+$", line) and len(line) < 60:
            return True
        return False

    @staticmethod
    def _is_line_number_prefix(line: str) -> bool:
        """代码行号前缀：` 123 | code` 或 `123: code` 形式。"""
        return bool(re.match(r"^\s*\d{1,5}\s*[|:]\s+\S", line))

    @staticmethod
    def _is_todo_comment(line: str) -> bool:
        """独立的 TODO/FIXME/XXX/HACK 注释行（保留含实际内容的注释）。"""
        if not re.match(r"^\s*[#*//]+\s*(TODO|FIXME|XXX|HACK)\b", line, re.IGNORECASE):
            return False
        # TODO 后内容过短则丢弃
        content = re.sub(r"^\s*[#*//]+\s*(TODO|FIXME|XXX|HACK)[:：]?\s*", "", line, flags=re.IGNORECASE)
        return len(content.strip()) < 20

    @staticmethod
    def _is_diff_marker_only(line: str) -> bool:
        """git diff 的纯 +/- 标记行（无实质内容）。"""
        if not re.match(r"^[+\-]\s*$", line):
            return False
        return True

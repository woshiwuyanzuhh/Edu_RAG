"""Markdown 解析器 — 保留代码块内容的纯文本提取（延迟导入 markdown 库）。"""

import re

from src.interfaces.parser import IParser
from src.shared.exceptions import ParseError


class MarkdownParser(IParser):
    @property
    def supported_extensions(self) -> set[str]:
        return {".md"}

    def parse(self, file_path: str) -> str:
        import markdown  # 延迟导入，避免不使用 .md 时强制安装

        try:
            with open(file_path, encoding="utf-8") as f:
                md_text = f.read()
        except Exception as e:
            raise ParseError(f"Markdown 文件读取失败: {file_path}", detail=str(e))

        # 1. 提取代码块内容并标记，避免被 HTML 转义丢失
        code_blocks: list[str] = []

        def _save_code_block(m: re.Match) -> str:
            code_blocks.append(m.group(2) or m.group(3))
            return f"\n<!--CODE_BLOCK_{len(code_blocks) - 1}-->\n"

        md_text = re.sub(r"```(?:\w+)?\s*\n(.*?)```", _save_code_block, md_text, flags=re.DOTALL)
        md_text = re.sub(r"`([^`]+)`", _save_code_block, md_text)

        # 2. HTML 转换 + 标签去除
        html = markdown.markdown(md_text)
        clean = re.sub(r"<[^>]+>", "", html)

        # 3. 恢复代码块
        for i, block in enumerate(code_blocks):
            clean = clean.replace(f"<!--CODE_BLOCK_{i}-->", block)

        return clean.strip()

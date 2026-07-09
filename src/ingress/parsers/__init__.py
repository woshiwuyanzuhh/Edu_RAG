"""文档解析器注册表 — 按扩展名分发。"""
from src.ingress.parsers.pdf import PDFParser
from src.ingress.parsers.docx import DocxParser
from src.ingress.parsers.markdown import MarkdownParser
from src.ingress.parsers.txt import TxtParser

# 解析器注册表: ext → IParser
PARSER_REGISTRY: dict[str, "IParser"] = {
    ".pdf": PDFParser(),
    ".docx": DocxParser(),
    ".doc": DocxParser(),
    ".md": MarkdownParser(),
    ".txt": TxtParser(),
}

__all__ = ["PDFParser", "DocxParser", "MarkdownParser", "TxtParser", "PARSER_REGISTRY"]

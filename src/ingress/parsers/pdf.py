"""PDF 解析器 — PyMuPDF。"""
import fitz  # PyMuPDF

from src.interfaces.parser import IParser
from src.shared.exceptions import ParseError


class PDFParser(IParser):
    @property
    def supported_extensions(self) -> set[str]:
        return {".pdf"}

    def parse(self, file_path: str) -> str:
        text_parts = []
        try:
            with fitz.open(file_path) as doc:
                for page in doc:
                    try:
                        text_parts.append(page.get_text())
                    except Exception:
                        text_parts.append("")  # 跳过损坏的页
        except Exception as e:
            raise ParseError(f"PDF 解析失败: {file_path}", detail=str(e))
        return "\n\n".join(text_parts).strip()

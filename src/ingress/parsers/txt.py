"""纯文本解析器。"""

from src.interfaces.parser import IParser
from src.shared.exceptions import ParseError


class TxtParser(IParser):
    @property
    def supported_extensions(self) -> set[str]:
        return {".txt"}

    def parse(self, file_path: str) -> str:
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            raise ParseError(f"文本文件读取失败: {file_path}", detail=str(e))

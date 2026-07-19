"""
递归语义文本切分器。

按分隔符优先级逐级切分，尽量在语义边界处断开：
    \\n\\n → \\n → 。→ .  → ！→ ？→ ；→ ;  → 空格 → 字符（兜底）

解决问题 #5 (分块决定检索上限): 保留元数据标注能力。
"""

from src.interfaces.chunker import IChunker


class RecursiveChunker(IChunker):
    """递归文本切分器：优先在语义边界切分，超长才降级到字符硬切。"""

    SEPARATORS = [
        "\n\n",
        "\r\n\r\n",
        "\n",
        "\r\n",
        "。",
        ". ",
        "！",
        "？",
        "；",
        "; ",
        " ",
        "",
    ]

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        self._chunk_size = max(chunk_size, 1)
        self._chunk_overlap = min(chunk_overlap, self._chunk_size - 1)

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._chunk_overlap

    def split(self, text: str) -> list[str]:
        if not text.strip():
            return []
        return self._split_recursive(text)

    def _split_recursive(self, text: str) -> list[str]:
        if len(text) <= self._chunk_size:
            return [text] if text.strip() else []

        for sep in self.SEPARATORS:
            if sep == "":
                return self._split_by_char(text)
            chunks = self._split_by_separator(text, sep)
            if len(chunks) > 1:
                result = []
                for chunk in chunks:
                    result.extend(self._split_recursive(chunk))
                return result

        return self._split_by_char(text)

    def _split_by_separator(self, text: str, sep: str) -> list[str]:
        parts = text.split(sep)
        chunks = []
        buffer = ""
        for part in parts:
            candidate = buffer + (sep if buffer else "") + part
            if len(candidate) > self._chunk_size:
                if buffer.strip():
                    chunks.append(buffer)
                buffer = part
            else:
                buffer = candidate

        if buffer.strip():
            chunks.append(buffer)

        if self._chunk_overlap > 0 and len(chunks) > 1:
            return self._merge_short_chunks(chunks)
        return chunks

    def _merge_short_chunks(self, chunks: list[str]) -> list[str]:
        merged = []
        for chunk in chunks:
            if merged and len(chunk) < self._chunk_overlap:
                merged[-1] = merged[-1] + chunk
            else:
                merged.append(chunk)
        return merged

    def _split_by_char(self, text: str) -> list[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + self._chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += self._chunk_size - self._chunk_overlap
        return chunks

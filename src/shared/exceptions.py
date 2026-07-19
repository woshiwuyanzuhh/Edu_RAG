"""
统一异常类层次 — 替代散落的 HTTPException + ValueError。
"""

from typing import Any


class EduRAGError(Exception):
    """edu_rag 基础异常。"""

    def __init__(self, message: str, detail: Any = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


# ── Ingestion 层异常 ──


class ParseError(EduRAGError):
    """文档解析失败。"""

    pass


class UnsupportedFileType(EduRAGError):
    """不支持的文件类型。"""

    pass


class FileTooLarge(EduRAGError):
    """文件超出大小限制。"""

    pass


class EmptyDocumentError(EduRAGError):
    """文档解析后无有效内容。"""

    pass


# ── Retrieval 层异常 ──


class EmbeddingError(EduRAGError):
    """Embedding 生成失败。"""

    pass


class VectorStoreError(EduRAGError):
    """向量库操作失败。"""

    pass


# ── Generation 层异常 ──


class LLMError(EduRAGError):
    """LLM 调用失败。"""

    pass


class LLMTimeoutError(LLMError):
    """LLM 调用超时。"""

    pass


class LLMRateLimitError(LLMError):
    """LLM API 频率限制。"""

    pass


class ParseLLMResponseError(EduRAGError):
    """LLM 返回的 JSON 无法解析。"""

    pass


# ── Orchestration 层异常 ──


class NotFoundError(EduRAGError):
    """资源不存在。"""

    pass


class UnauthorizedError(EduRAGError):
    """未授权访问。"""

    pass


class ValidationError(EduRAGError):
    """输入校验失败。"""

    pass

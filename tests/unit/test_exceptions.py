"""统一异常类层次测试 — src/shared/exceptions.py。"""
import pytest
from src.shared.exceptions import (
    EduRAGError,
    ParseError, UnsupportedFileType, FileTooLarge, EmptyDocumentError,
    EmbeddingError, VectorStoreError,
    LLMError, LLMTimeoutError, LLMRateLimitError, ParseLLMResponseError,
    NotFoundError, UnauthorizedError, ValidationError,
)


class TestEduRAGError:
    """基础异常类测试。"""

    def test_basic_message(self):
        e = EduRAGError("测试错误")
        assert str(e) == "测试错误"
        assert e.message == "测试错误"
        assert e.detail is None

    def test_with_detail(self):
        e = EduRAGError("验证失败", detail={"field": "name", "reason": "必填"})
        assert e.message == "验证失败"
        assert e.detail == {"field": "name", "reason": "必填"}

    def test_is_exception(self):
        e = EduRAGError("test")
        assert isinstance(e, Exception)


class TestIngestionExceptions:
    """写入层异常。"""

    def test_parse_error(self):
        e = ParseError("PDF 解析失败", detail="page 3 corrupted")
        assert isinstance(e, EduRAGError)
        assert e.message == "PDF 解析失败"

    def test_unsupported_file_type(self):
        e = UnsupportedFileType("不支持的文件类型: .xyz")
        assert isinstance(e, EduRAGError)

    def test_file_too_large(self):
        e = FileTooLarge("文件大小超出限制 50MB")
        assert isinstance(e, EduRAGError)

    def test_empty_document(self):
        e = EmptyDocumentError("文档解析后无内容")
        assert isinstance(e, EduRAGError)


class TestRetrievalExceptions:
    """检索层异常。"""

    def test_embedding_error(self):
        e = EmbeddingError("Embedding 生成失败")
        assert isinstance(e, EduRAGError)

    def test_vector_store_error(self):
        e = VectorStoreError("向量库连接超时")
        assert isinstance(e, EduRAGError)


class TestGenerationExceptions:
    """生成层异常。"""

    def test_llm_error(self):
        e = LLMError("API 调用失败")
        assert isinstance(e, EduRAGError)

    def test_llm_timeout_is_llm_error(self):
        e = LLMTimeoutError("请求超时")
        assert isinstance(e, LLMError)
        assert isinstance(e, EduRAGError)

    def test_llm_rate_limit_is_llm_error(self):
        e = LLMRateLimitError("频率限制")
        assert isinstance(e, LLMError)

    def test_parse_llm_response_error(self):
        e = ParseLLMResponseError("JSON 解析失败")
        assert isinstance(e, EduRAGError)


class TestOrchestrationExceptions:
    """编排层异常。"""

    def test_not_found(self):
        e = NotFoundError("知识库不存在")
        assert isinstance(e, EduRAGError)

    def test_unauthorized(self):
        e = UnauthorizedError("API Key 无效")
        assert isinstance(e, EduRAGError)

    def test_validation_error(self):
        e = ValidationError("知识库名称为必填")
        assert isinstance(e, EduRAGError)

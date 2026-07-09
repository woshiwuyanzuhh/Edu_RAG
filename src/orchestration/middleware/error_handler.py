"""
全局异常处理器 — 统一错误响应格式。
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse

from src.shared.exceptions import (
    EduRAGError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    ParseError,
    UnsupportedFileType,
    FileTooLarge,
    EmptyDocumentError,
    LLMError,
)
from src.shared.models.schemas import APIResponse
from src.observability import get_request_id

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError):
        return ORJSONResponse(
            status_code=404,
            content=APIResponse(success=False, message=exc.message).model_dump(),
        )

    @app.exception_handler(UnauthorizedError)
    async def handle_unauthorized(request: Request, exc: UnauthorizedError):
        return ORJSONResponse(
            status_code=401,
            content=APIResponse(success=False, message=exc.message).model_dump(),
        )

    @app.exception_handler(ValidationError)
    async def handle_validation(request: Request, exc: ValidationError):
        return ORJSONResponse(
            status_code=400,
            content=APIResponse(success=False, message=exc.message).model_dump(),
        )

    @app.exception_handler(ParseError)
    @app.exception_handler(UnsupportedFileType)
    @app.exception_handler(FileTooLarge)
    @app.exception_handler(EmptyDocumentError)
    async def handle_ingestion_errors(request: Request, exc: EduRAGError):
        return ORJSONResponse(
            status_code=400,
            content=APIResponse(success=False, message=exc.message).model_dump(),
        )

    @app.exception_handler(LLMError)
    async def handle_llm_error(request: Request, exc: LLMError):
        logger.error(f"llm_error request_id={get_request_id()} error={exc}")
        return ORJSONResponse(
            status_code=502,
            content=APIResponse(success=False, message=f"LLM 服务异常: {exc.message}").model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception(f"unexpected_error request_id={get_request_id()} error={exc}")
        return ORJSONResponse(
            status_code=500,
            content=APIResponse(success=False, message="服务器内部错误").model_dump(),
        )

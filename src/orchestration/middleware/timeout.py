"""请求超时中间件 — 防止慢请求占满 worker。

SSE 流式端点（/api/qa/stream, /api/exam/generate/stream）豁免超时，
因为它们是长连接流式响应，天然耗时较长。

非流式请求超过 request_timeout 秒后返回 504 Gateway Timeout。
"""

import asyncio
import logging

from fastapi import Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.config import settings

logger = logging.getLogger(__name__)

# SSE 流式端点豁免超时
_STREAM_PATHS = frozenset(
    {
        "/api/qa/stream",
        "/api/exam/generate/stream",
    }
)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """全局请求超时保护。

    配置: APP__REQUEST_TIMEOUT（秒，默认 30）
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # SSE 流式端点豁免
        if path in _STREAM_PATHS:
            return await call_next(request)

        timeout = settings.app.request_timeout
        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"request_timeout path={path} timeout={timeout}s request_id={request.headers.get('X-Request-ID', '-')}"
            )
            return ORJSONResponse(
                status_code=504,
                content={
                    "success": False,
                    "message": f"请求处理超时（{timeout}秒），请稍后重试",
                    "data": None,
                },
            )

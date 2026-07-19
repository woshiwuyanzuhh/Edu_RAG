"""
X-Request-ID 中间件 — 全链路追踪。

解决问题 #4: 日志中注入 request_id，方便串联一次请求的所有日志。
"""

import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.observability import set_request_id

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 X-Request-ID。"""

    async def dispatch(self, request: Request, call_next):
        # 优先使用客户端传入的 ID，否则生成新的
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        set_request_id(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

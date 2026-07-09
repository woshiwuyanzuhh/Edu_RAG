"""
API Key 鉴权中间件。

解决问题 #3: 缺乏鉴权与访问控制。

短期方案: X-API-Key Header 校验。
中长期: JWT + RBAC。
"""
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.config import settings

logger = logging.getLogger(__name__)

# 无需鉴权的路径
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key 鉴权中间件。

    可通过 X-API-Key Header 或 ?api_key=xxx Query 参数传递。
    如果 APP_API_KEY 配置为空，则跳过鉴权（兼容开发环境）。
    """

    async def dispatch(self, request: Request, call_next):
        # 静态文件和公开路径跳过
        path = request.url.path
        if path.startswith("/static") or path in PUBLIC_PATHS:
            return await call_next(request)

        # 如果未配置 API Key，跳过鉴权（开发模式）
        api_key = settings.app.api_key.get_secret_value()
        if not api_key:
            return await call_next(request)

        # 从 Header 或 Query 获取
        provided_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

        if not provided_key or provided_key != api_key:
            logger.warning(f"auth_failed path={path} ip={request.client.host if request.client else 'unknown'}")
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "未授权访问，请提供有效的 API Key", "data": None},
            )

        return await call_next(request)

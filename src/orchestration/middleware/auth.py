"""
API Key 鉴权中间件。

解决问题 #3: 缺乏鉴权与访问控制。

短期方案: X-API-Key Header 校验（fail-closed）。
中长期: JWT + RBAC。

安全策略:
    - 仅允许 X-API-Key 请求头传递密钥（不再支持 Query 参数，避免日志/Referer 泄露）
    - 生产模式（debug=False）下未配置 API Key 时拒绝所有非公开请求（fail-closed）
    - 开发模式（debug=True）下未配置 API Key 时跳过鉴权，便于本地调试
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
    """API Key 鉴权中间件（fail-closed）。

    通过 X-API-Key 请求头校验。
    - 生产模式（debug=False）：未配置 API Key 时拒绝所有非公开请求
    - 开发模式（debug=True）：未配置 API Key 时跳过鉴权
    """

    async def dispatch(self, request: Request, call_next):
        # 静态文件和公开路径跳过
        path = request.url.path
        if path.startswith("/static") or path in PUBLIC_PATHS:
            return await call_next(request)

        api_key = settings.app.api_key.get_secret_value()

        # fail-closed: 未配置 API Key 时的处理
        if not api_key:
            if settings.app.debug:
                # 开发模式：跳过鉴权，仅告警
                logger.debug("auth_skipped_debug_mode path=%s", path)
                return await call_next(request)
            # 生产模式：拒绝访问（fail-closed）
            logger.error("auth_blocked_no_api_key path=%s ip=%s", path,
                         request.client.host if request.client else "unknown")
            return JSONResponse(
                status_code=503,
                content={"success": False, "message": "服务未配置鉴权密钥，拒绝访问", "data": None},
            )

        # 仅从 Header 获取（不再支持 Query 参数，避免日志泄露）
        provided_key = request.headers.get("X-API-Key")

        if not provided_key or provided_key != api_key:
            logger.warning("auth_failed path=%s ip=%s", path,
                           request.client.host if request.client else "unknown")
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "未授权访问，请提供有效的 API Key", "data": None},
            )

        return await call_next(request)

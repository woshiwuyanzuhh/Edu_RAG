"""Rate Limiting 中间件 — 基于 Redis 的滑动窗口限流。

API 端点差异化限制：
    - /api/qa/*   → LLM 调用接口，更严格
    - /api/exam/* → LLM 调用接口，更严格
    - /api/*      → 普通 API 接口
"""
import time
import logging
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.config import settings
from src.shared.database.redis import redis_client

logger = logging.getLogger(__name__)


def _get_limits(path: str) -> tuple[int, int]:
    """根据路径返回 (max_requests, window_seconds)，从配置读取。"""
    cfg = settings.app
    if path.startswith("/api/qa") or path.startswith("/api/exam"):
        return cfg.rate_limit_llm, cfg.rate_limit_window
    return cfg.rate_limit_default, cfg.rate_limit_window


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流中间件。

    依赖 Redis。Redis 不可用时自动放行（不阻塞请求）。
    """

    async def dispatch(self, request: Request, call_next):
        # 限流开关：压测/调试时可关闭
        if not settings.app.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path

        # 公开路径跳过
        if path in ("/health", "/metrics", "/docs", "/openapi.json", "/redoc", "/favicon.ico"):
            return await call_next(request)
        if path.startswith("/static") or path.startswith("/assets"):
            return await call_next(request)

        if not redis_client.is_connected:
            return await call_next(request)

        max_req, window = _get_limits(path)

        # 构造限流 key：按 IP + 路径分组
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"rate_limit:{client_ip}:{path}"

        try:
            now = time.time()
            window_start = now - window

            # 滑动窗口：删除过期记录 + 计数
            await redis_client.client.zremrangebyscore(rate_key, 0, window_start)
            count = await redis_client.client.zcard(rate_key)

            if count >= max_req:
                logger.warning(f"rate_limited ip={client_ip} path={path} count={count}")
                return JSONResponse(
                    status_code=429,
                    content={"success": False, "message": f"请求过于频繁，请 {window} 秒后重试", "data": None},
                )

            # 记录本次请求 — member 用 uuid 保证唯一，避免同毫秒同 IP 重复请求覆盖
            await redis_client.client.zadd(rate_key, {str(uuid.uuid4()): now})
            await redis_client.client.expire(rate_key, window + 10)

        except Exception as e:
            logger.warning(f"rate_limit_check_failed error={e} — passing through")
            # Redis 异常时放行

        return await call_next(request)

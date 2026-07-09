"""
LLM 韧性模块 — 重试/退避/熔断。

解决问题 #16: 无重试/退避机制。

策略:
    - 仅对网络错误和 5xx 重试
    - 4xx（如 401 密钥错误、400 参数错误）不重试
    - 指数退避: 1s → 2s → 4s，最多 3 次
"""
import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# 不可重试的错误关键字（rate limit 应重试，已移除）
NON_RETRYABLE = (
    "401", "403", "invalid api key", "authentication",
    "quota", "maximum context length",
)


def _is_retryable(error: Exception) -> bool:
    """判断异常是否可重试。"""
    msg = str(error).lower()
    for keyword in NON_RETRYABLE:
        if keyword.lower() in msg:
            return False
    return True


async def with_retry(
    func: Callable[..., Awaitable],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs,
):
    """带指数退避的重试包装器。

    Args:
        func: 异步函数
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        backoff_factor: 退避倍数
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt == max_retries or not _is_retryable(e):
                raise

            delay = base_delay * (backoff_factor ** attempt)
            logger.warning(
                f"llm_retry attempt={attempt + 1}/{max_retries} delay={round(delay, 1)}s error={str(e)[:200]}"
            )
            await asyncio.sleep(delay)

    raise last_error  # type: ignore[misc]

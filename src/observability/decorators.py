"""可观测性装饰器 — 通过 @traced 自动注入 Tracing，替代手动 span 编写。

解决问题：原则 — 可观测性应该是基础设施层的能力，通过装饰器注入，不侵入业务代码。
"""
import time
import functools
import logging
from typing import Callable

logger = logging.getLogger(__name__)


def traced(name: str | None = None):
    """异步函数追踪装饰器。

    自动记录函数调用耗时并输出结构化日志。可与现有 Tracer 配合使用。

    用法：
        @traced("recall")
        async def recall(query, embedder, vector_store, ...):
            ...

    日志输出：
        trace name=recall duration_ms=45.2 status=ok
    """
    def decorator(func: Callable):
        span_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                logger.debug(f"trace name={span_name} duration_ms={duration_ms:.1f} status=ok")
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.warning(f"trace name={span_name} duration_ms={duration_ms:.1f} status=error error={e}")
                raise

        return wrapper

    return decorator


def traced_sync(name: str | None = None):
    """同步函数追踪装饰器（用于 to_thread 包装的函数）。"""
    def decorator(func: Callable):
        span_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                logger.debug(f"trace name={span_name} duration_ms={duration_ms:.1f} status=ok")
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.warning(f"trace name={span_name} duration_ms={duration_ms:.1f} status=error error={e}")
                raise

        return wrapper

    return decorator

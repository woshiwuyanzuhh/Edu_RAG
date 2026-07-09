"""
缓存模块 — Redis 缓存策略 + 装饰器。

解决问题 #1: Redis 已连接但完全未使用。
"""
import json
import hashlib
import functools
import logging
from typing import Any, Callable

from src.shared.config import settings

logger = logging.getLogger(__name__)

# 全局 Redis 客户端引用（在 lifespan 中注入）
_redis_client: Any = None


def set_redis_client(client: Any) -> None:
    """注入 Redis 客户端。"""
    global _redis_client
    _redis_client = client


def _get_redis():
    if _redis_client is None:
        raise RuntimeError("Redis 未初始化，请先调用 set_redis_client()")
    return _redis_client


# ── 缓存键生成 ──

def make_cache_key(prefix: str, *args, **kwargs) -> str:
    """生成确定性的缓存键。

    Args:
        prefix: 缓存键前缀（如 "qa", "embedding", "query_expand"）
        *args: 位置参数
        **kwargs: 关键字参数
    """
    payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, ensure_ascii=False)
    digest = hashlib.md5(payload.encode()).hexdigest()[:12]
    return f"edu_rag:{prefix}:{digest}"


# ── 异步缓存装饰器 ──

def async_cached(prefix: str, ttl: int | None = None):
    """异步函数结果缓存装饰器。

    用法：
        @async_cached("query_expand", ttl=600)
        async def expand_queries(question: str) -> list[str]:
            ...

    Args:
        prefix: 缓存键前缀
        ttl: 过期时间（秒），默认使用 settings.redis.default_ttl
    """
    _ttl = ttl or settings.redis.default_ttl

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 先获取 Redis（提前处理 RuntimeError）
            try:
                redis = _get_redis()
            except RuntimeError:
                # Redis 未初始化，降级：直接调用函数
                return await func(*args, **kwargs)

            key = make_cache_key(prefix, func.__name__, *args, **kwargs)
            try:
                cached = await redis.get(key)
                if cached is not None:
                    logger.debug(f"cache_hit prefix={prefix} key={key}")
                    return json.loads(cached)
            except Exception:
                logger.warning(f"cache_read_error prefix={prefix}", exc_info=True)

            # 执行函数（仅一次）
            result = await func(*args, **kwargs)

            # 尝试写缓存，失败不影响返回结果
            try:
                await redis.set(key, json.dumps(result, ensure_ascii=False), ex=_ttl)
                logger.debug(f"cache_set prefix={prefix} key={key} ttl={_ttl}")
            except Exception:
                logger.warning(f"cache_write_error prefix={prefix}", exc_info=True)

            return result

        return wrapper

    return decorator


# ── 多级缓存策略 ──

class CacheStrategy:
    """多级缓存策略管理器。

    层次：
        L1: 进程内字典（极快，秒级 TTL，适合 Embedding）
        L2: Redis（快，分钟级 TTL，适合检索结果、LLM 调用）
    """

    def __init__(self):
        self._l1: dict[str, tuple[Any, float]] = {}
        self._l1_ttl: float = 60.0  # L1 默认 60 秒

    async def get(self, key: str) -> Any | None:
        """先查 L1，再查 L2。"""
        import time

        # L1 查询
        if key in self._l1:
            value, expire_at = self._l1[key]
            if time.time() < expire_at:
                return value
            del self._l1[key]

        # L2 查询
        try:
            redis = _get_redis()
            raw = await redis.get(key)
            if raw:
                value = json.loads(raw)
                self._l1[key] = (value, time.time() + self._l1_ttl)
                return value
        except (RuntimeError, Exception):
            pass

        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """同时写 L1 和 L2。"""
        import time

        _ttl = ttl or settings.redis.default_ttl
        self._l1[key] = (value, time.time() + min(self._l1_ttl, _ttl))

        try:
            redis = _get_redis()
            await redis.set(key, json.dumps(value, ensure_ascii=False), ex=_ttl)
        except (RuntimeError, Exception):
            pass

    async def invalidate(self, pattern: str) -> None:
        """失效指定模式的缓存。"""
        self._l1.clear()
        try:
            redis = _get_redis()
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
        except (RuntimeError, Exception):
            pass


# 全局缓存策略实例
cache_strategy = CacheStrategy()

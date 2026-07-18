"""
Redis 缓存客户端 — 异步 Redis + JSON 便捷方法。

解决问题 #1: 这是新架构中实际被使用的 Redis 客户端。
"""
import json
import logging
import warnings
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

from src.shared.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """异步 Redis 客户端封装。"""

    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> bool:
        """连接 Redis，返回是否成功。"""
        try:
            self._redis = aioredis.Redis(**settings.redis.connection_kwargs)
            await self._redis.ping()
            logger.info(f"redis_connected host={settings.redis.host} port={settings.redis.port}")
            return True
        except Exception as e:
            logger.warning(f"redis_connection_failed error={e}")
            self._redis = None
            return False

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("redis_disconnected")

    @property
    def client(self) -> aioredis.Redis:
        if self._redis is None:
            raise RuntimeError("Redis 未连接")
        return self._redis

    @property
    def is_connected(self) -> bool:
        return self._redis is not None

    # ── 缓存便捷方法 ──

    async def get(self, key: str) -> str | None:
        """获取字符串值。"""
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ex: int = 3600) -> bool:
        """设置字符串值（带 TTL）。"""
        if not self._redis:
            return False
        try:
            await self._redis.set(key, value, ex=ex)
            return True
        except Exception:
            return False

    async def get_json(self, key: str) -> Any | None:
        """获取 JSON 值。"""
        raw = await self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置 JSON 值。"""
        return await self.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)

    async def delete(self, *keys: str) -> bool:
        """删除键。"""
        if not self._redis or not keys:
            return False
        try:
            await self._redis.delete(*keys)
            return True
        except Exception:
            return False

    async def keys(self, pattern: str) -> list[str]:
        """按模式查询键列表。

        .. deprecated::
            KEYS 命令在生产环境会阻塞 Redis，请改用 scan()。
        """
        warnings.warn(
            "RedisClient.keys() 使用 KEYS 命令，生产环境会阻塞 Redis。"
            "请改用 scan() 方法（基于 SCAN，非阻塞）。",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self._redis:
            return []
        try:
            return await self._redis.keys(pattern)
        except Exception:
            return []

    async def scan(self, pattern: str, count: int = 200) -> AsyncIterator[str]:
        """按模式增量扫描键（推荐替代 keys()）。

        使用 SCAN 命令，非阻塞，适合生产环境。

        Args:
            pattern: 匹配模式（如 "edu_rag:*:1:*"）
            count: 每次迭代的批次大小（默认 200）

        Yields:
            匹配的键名
        """
        if not self._redis:
            return
        try:
            async for key in self._redis.scan_iter(match=pattern, count=count):
                yield key
        except Exception:
            return


# 全局实例
redis_client = RedisClient()

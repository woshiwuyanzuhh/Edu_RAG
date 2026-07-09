"""
Redis 缓存客户端 — 异步 Redis + JSON 便捷方法。

解决问题 #1: 这是新架构中实际被使用的 Redis 客户端。
"""
import json
import logging
from typing import Any

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
        """按模式查询键列表。"""
        if not self._redis:
            return []
        try:
            return await self._redis.keys(pattern)
        except Exception:
            return []


# 全局实例
redis_client = RedisClient()

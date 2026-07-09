"""缓存模块测试 — src/shared/cache.py。"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from src.shared.cache import (
    make_cache_key,
    async_cached,
    CacheStrategy,
    set_redis_client,
    _get_redis,
)


class TestMakeCacheKey:
    """缓存键生成。"""

    def test_basic(self):
        key = make_cache_key("qa", "什么是RAG", top_k=5)
        assert key.startswith("edu_rag:qa:")
        assert len(key.split(":")[-1]) == 12  # md5[:12]

    def test_same_args_same_key(self):
        k1 = make_cache_key("qa", "问题", kbid=1)
        k2 = make_cache_key("qa", "问题", kbid=1)
        assert k1 == k2

    def test_different_args_different_key(self):
        k1 = make_cache_key("qa", "问题1")
        k2 = make_cache_key("qa", "问题2")
        assert k1 != k2

    def test_args_order_matters(self):
        """JSON sort_keys 确保参数顺序不影响 key。"""
        k1 = make_cache_key("qa", a=1, b=2)
        k2 = make_cache_key("qa", b=2, a=1)
        assert k1 == k2

    def test_chinese_text(self):
        key = make_cache_key("query_expand", "什么是机器学习")
        assert isinstance(key, str)
        assert key.startswith("edu_rag:")


class TestSetRedisClient:
    """Redis 客户端注入。"""

    def test_set_and_get_redis(self):
        mock_client = MagicMock()
        set_redis_client(mock_client)
        assert _get_redis() == mock_client

    def test_get_redis_uninitialized(self):
        """未初始化时抛出 RuntimeError。"""
        set_redis_client(None)
        with pytest.raises(RuntimeError, match="Redis 未初始化"):
            _get_redis()


class TestCacheStrategy:
    """多级缓存策略 L1 + L2 — 使用 asyncio.run() 模式。"""

    @pytest.fixture
    def strategy(self):
        s = CacheStrategy()
        s._l1_ttl = 5.0  # 缩短 L1 TTL 以便测试
        return s

    def test_get_miss(self, strategy):
        with patch("src.shared.cache._get_redis", side_effect=RuntimeError):
            result = asyncio.run(strategy.get("nonexistent"))
            assert result is None

    def test_set_and_get_l1(self, strategy):
        asyncio.run(strategy.set("test:key", {"data": "hello"}, ttl=600))
        result = asyncio.run(strategy.get("test:key"))
        assert result == {"data": "hello"}

    def test_l1_expiry(self, strategy):
        """手动设置一个已过期的 L1 缓存。"""
        strategy._l1["expired:key"] = ({"old": "data"}, time.time() - 10)
        result = asyncio.run(strategy.get("expired:key"))
        assert result is None  # 已过期
        assert "expired:key" not in strategy._l1  # 已清理

    def test_l2_fallback(self, strategy):
        """L1 未命中时查 L2，并回填 L1。"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"from": "redis"}'
        with patch("src.shared.cache._get_redis", return_value=mock_redis):
            result = asyncio.run(strategy.get("l2:key"))
            assert result == {"from": "redis"}
            # 回填到 L1
            assert "l2:key" in strategy._l1

    def test_invalidate_clears_l1(self, strategy):
        asyncio.run(strategy.set("key:a", "val_a"))
        asyncio.run(strategy.set("key:b", "val_b"))
        assert len(strategy._l1) == 2
        with patch("src.shared.cache._get_redis", side_effect=RuntimeError):
            asyncio.run(strategy.invalidate("key:*"))
        assert len(strategy._l1) == 0

    def test_invalidate_redis_keys(self, strategy):
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = ["key:a", "key:b"]
        with patch("src.shared.cache._get_redis", return_value=mock_redis):
            asyncio.run(strategy.invalidate("key:*"))
            mock_redis.keys.assert_called_once_with("key:*")
            mock_redis.delete.assert_called_once_with("key:a", "key:b")

    def test_l1_ttl_respected(self, strategy):
        strategy._l1_ttl = 60.0
        asyncio.run(strategy.set("k", "v", ttl=30))
        # value, expire_at — L1 TTL = min(60, 30) = 30s
        val, expire = strategy._l1["k"]
        assert val == "v"
        assert expire - time.time() <= 30


class TestAsyncCached:
    """@async_cached 装饰器 — 使用 asyncio.run() 模式。"""

    def test_cache_hit_skip_function(self):
        """缓存命中时不执行原函数。"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '["cached_result"]'
        set_redis_client(mock_redis)

        call_count = [0]

        @async_cached("test_hit", ttl=600)
        async def expensive_call(x):
            call_count[0] += 1
            return [f"result_{x}"]

        result = asyncio.run(expensive_call("input"))
        assert result == ["cached_result"]
        assert call_count[0] == 0  # 原函数未被调用

    def test_cache_miss_calls_function_and_caches(self):
        """缓存未命中时执行原函数并缓存结果。"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss
        set_redis_client(mock_redis)

        @async_cached("test_miss", ttl=600)
        async def compute(x):
            return [f"computed_{x}"]

        result = asyncio.run(compute("data"))
        assert result == ["computed_data"]
        # 验证写入了缓存
        mock_redis.set.assert_called_once()

    def test_redis_unavailable_fallback(self):
        """Redis 不可用时降级为直接调用原函数。"""
        set_redis_client(None)  # 未初始化

        call_count = [0]

        @async_cached("test_fallback", ttl=600)
        async def fallback_func(x):
            call_count[0] += 1
            return [f"fallback_{x}"]

        result = asyncio.run(fallback_func("emergency"))
        assert result == ["fallback_emergency"]
        assert call_count[0] == 1

    def test_cache_read_error_not_fatal(self):
        """读取缓存出错时仍执行原函数。"""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis read error")
        set_redis_client(mock_redis)

        @async_cached("test_read_err", ttl=600)
        async def resilient_func(x):
            return [f"resilient_{x}"]

        result = asyncio.run(resilient_func("input"))
        assert result == ["resilient_input"]

    def test_cache_write_error_not_fatal(self):
        """写入缓存出错时不影响结果返回。"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.set.side_effect = Exception("Redis write error")
        set_redis_client(mock_redis)

        @async_cached("test_write_err", ttl=600)
        async def compute(x):
            return [f"result_{x}"]

        result = asyncio.run(compute("input"))
        assert result == ["result_input"]

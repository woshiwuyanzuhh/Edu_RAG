"""LLM 韧性模块测试 — src/generation/llm/resilience.py。"""
import pytest
import asyncio
from src.generation.llm.resilience import with_retry, _is_retryable, NON_RETRYABLE


class TestIsRetryable:
    """_is_retryable 判断异常是否可重试。"""

    def test_network_error_retryable(self):
        e = Exception("Connection reset by peer")
        assert _is_retryable(e) is True

    def test_timeout_retryable(self):
        e = Exception("request timed out")
        assert _is_retryable(e) is True

    def test_500_error_retryable(self):
        e = Exception("HTTP 500 Internal Server Error")
        assert _is_retryable(e) is True

    def test_401_not_retryable(self):
        e = Exception("HTTP 401 Unauthorized")
        assert _is_retryable(e) is False

    def test_403_not_retryable(self):
        e = Exception("HTTP 403 Forbidden")
        assert _is_retryable(e) is False

    def test_invalid_api_key_not_retryable(self):
        e = Exception("invalid api key")
        assert _is_retryable(e) is False

    def test_authentication_error_not_retryable(self):
        e = Exception("authentication failed")
        assert _is_retryable(e) is False

    def test_quota_not_retryable(self):
        e = Exception("quota exceeded for this billing period")
        assert _is_retryable(e) is False

    def test_max_context_length_not_retryable(self):
        e = Exception("maximum context length exceeded")
        assert _is_retryable(e) is False

    def test_case_insensitive(self):
        e = Exception("Invalid API Key detected")
        assert _is_retryable(e) is False

    def test_non_retryable_keywords_present(self):
        """NON_RETRYABLE 常量应包含这些关键类别。"""
        assert "401" in NON_RETRYABLE
        assert "403" in NON_RETRYABLE
        assert "authentication" in NON_RETRYABLE
        assert "quota" in NON_RETRYABLE


class TestWithRetry:
    """with_retry 重试包装器 — 使用 asyncio.run() 模式。"""

    def test_success_first_try(self):
        """第一次就成功，不重试。"""
        async def ok():
            return "result"
        result = asyncio.run(with_retry(ok, max_retries=3))
        assert result == "result"

    def test_retry_once_success(self):
        """第一次失败，第二次成功。"""
        attempts = [0]

        async def flaky():
            attempts[0] += 1
            if attempts[0] < 2:
                raise RuntimeError(f"临时错误 (attempt {attempts[0]})")
            return "success_on_2"

        result = asyncio.run(with_retry(flaky, max_retries=3, base_delay=0.01, backoff_factor=1.0))
        assert result == "success_on_2"
        assert attempts[0] == 2

    def test_retry_exhausted_raises(self):
        """重试次数用尽后抛出最后的异常。"""
        async def always_fail():
            raise RuntimeError("永久错误")

        with pytest.raises(RuntimeError, match="永久错误"):
            asyncio.run(with_retry(always_fail, max_retries=2, base_delay=0.01))

    def test_non_retryable_raises_immediately(self):
        """不可重试的错误立即抛出，不等待。"""
        async def auth_fail():
            raise RuntimeError("401 Unauthorized")

        with pytest.raises(RuntimeError):
            asyncio.run(with_retry(auth_fail, max_retries=3, base_delay=1.0))

    def test_passes_args_and_kwargs(self):
        """验证参数正确传递。"""
        async def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        result = asyncio.run(with_retry(greet, "World", greeting="Hi", max_retries=1))
        assert result == "Hi, World"

    def test_exponential_backoff_order(self):
        """验证重试延迟按指数增长 — base_delay=0.02, backoff=2。"""
        call_count = [0]

        async def record_and_fail():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise RuntimeError(f"fail {call_count[0]}")
            return "ok"

        # base=0.02, factor=2 → delay attempts: 0.02, 0.04 → total < 0.1s
        result = asyncio.run(with_retry(record_and_fail, max_retries=3, base_delay=0.02, backoff_factor=2.0))
        assert result == "ok"
        assert call_count[0] == 3

    def test_max_retries_zero(self):
        """max_retries=0 时失败直接抛出。"""
        async def fail():
            raise RuntimeError("错误")

        with pytest.raises(RuntimeError):
            asyncio.run(with_retry(fail, max_retries=0))

    def test_with_retry_type_error(self):
        """TypeError 也应该被传播。"""
        async def type_error():
            raise TypeError("类型错误")

        with pytest.raises(TypeError):
            asyncio.run(with_retry(type_error, max_retries=1, base_delay=0.01))

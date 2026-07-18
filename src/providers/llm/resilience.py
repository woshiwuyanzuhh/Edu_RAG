"""Retry helpers for LLM providers."""
import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# Errors that should fail fast. Rate limits are intentionally retryable.
NON_RETRYABLE = (
    "401", "403", "invalid api key", "authentication",
    "quota", "maximum context length",
)


def _is_retryable(error: Exception) -> bool:
    """Return whether an LLM provider error should be retried."""
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
    """Run an async callable with exponential backoff."""
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

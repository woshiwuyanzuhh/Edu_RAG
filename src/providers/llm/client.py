"""OpenAI-compatible LLM client provider.

使用原生 AsyncOpenAI SDK，避免同步 SDK + to_thread/threading 的线程开销。
"""
import asyncio
import logging

from openai import AsyncOpenAI

from src.interfaces.llm import ILLMClient, Message
from src.providers.llm.resilience import _is_retryable, with_retry
from src.shared.config import settings

logger = logging.getLogger(__name__)


class OpenAICompatClient(ILLMClient):
    """Client for OpenAI-compatible chat completion APIs (async native)."""

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.llm.api_key.get_secret_value(),
            base_url=settings.llm.base_url,
            timeout=60.0,
        )

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

        async def _call():
            response = await self._client.chat.completions.create(
                model=settings.llm.model,
                messages=msg_dicts,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        try:
            return await with_retry(
                _call,
                max_retries=settings.llm.max_retries,
                base_delay=1.0,
                backoff_factor=settings.llm.retry_backoff,
            )
        except Exception as e:
            logger.error(f"llm_chat_failed error={e} model={settings.llm.model}")
            raise

    async def chat_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

        max_retries = settings.llm.max_retries
        backoff = settings.llm.retry_backoff

        for attempt in range(max_retries + 1):
            # ── 连接阶段：建立流，失败可重试 ──
            try:
                stream = await self._client.chat.completions.create(
                    model=settings.llm.model,
                    messages=msg_dicts,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    timeout=60.0,
                )
            except Exception as e:
                if attempt < max_retries and _is_retryable(e):
                    delay = 1.0 * (backoff ** attempt)
                    logger.warning(
                        f"stream_retry attempt={attempt + 1}/{max_retries} "
                        f"delay={delay:.1f}s error={e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"llm_stream_connect_failed error={e}")
                raise

            # ── 消费阶段：流已建立，不重试（已 yield 的数据不可撤回）──
            try:
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
            except Exception as e:
                logger.error(f"llm_stream_interrupted error={e}")
                raise
            return

"""OpenAI-compatible LLM client provider.

使用原生 AsyncOpenAI SDK，避免同步 SDK + to_thread/threading 的线程开销。
通过 asyncio.Semaphore 限制并发请求数，防止压测时触发 LLM API 速率限制。
"""

import asyncio
import logging

from openai import AsyncOpenAI

from src.interfaces.llm import ILLMClient, Message
from src.observability.metrics import LLM_LATENCY
from src.providers.llm.resilience import _is_retryable, with_retry
from src.shared.config import settings

logger = logging.getLogger(__name__)


class OpenAICompatClient(ILLMClient):
    """Client for OpenAI-compatible chat completion APIs (async native).

    并发控制: 通过全局 Semaphore 限制同时在飞的 LLM 请求数。
    配置: LLM__MAX_CONCURRENCY（默认 10）。
    """

    # 类级 Semaphore — 所有实例共享，确保多服务单例统一限流
    _semaphore: asyncio.Semaphore | None = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """惰性初始化 Semaphore（需在事件循环内创建）。"""
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(settings.llm.max_concurrency)
            logger.info(f"llm_concurrency_limit set to {settings.llm.max_concurrency}")
        return cls._semaphore

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
        sem = self._get_semaphore()

        async def _call():
            async with sem:
                with LLM_LATENCY.labels(model=settings.llm.model).time():
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
        sem = self._get_semaphore()

        for attempt in range(max_retries + 1):
            # ── 连接阶段：建立流，失败可重试 ──
            try:
                async with sem:
                    stream = await self._client.chat.completions.create(
                        model=settings.llm.model,
                        messages=msg_dicts,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True,
                        timeout=60.0,
                    )
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
            except Exception as e:
                if attempt < max_retries and _is_retryable(e):
                    delay = 1.0 * (backoff**attempt)
                    logger.warning(f"stream_retry attempt={attempt + 1}/{max_retries} delay={delay:.1f}s error={e}")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"llm_stream_connect_failed error={e}")
                raise

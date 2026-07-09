"""
OpenAI 兼容 LLM 客户端 — 含超时和重试。

支持 DeepSeek、OpenAI、vLLM 等任何 OpenAI 兼容 API。
"""
import asyncio
import threading
import logging
from openai import OpenAI

from src.interfaces.llm import ILLMClient, Message
from src.shared.config import settings
from src.generation.llm.resilience import with_retry

logger = logging.getLogger(__name__)


class OpenAICompatClient(ILLMClient):
    """OpenAI 兼容 API 客户端 — 含超时和自动重试。"""

    def __init__(self):
        self._client = OpenAI(
            api_key=settings.llm.api_key.get_secret_value(),
            base_url=settings.llm.base_url,
            timeout=60.0,  # 单次请求 60 秒超时
        )

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

        def _sync_call():
            response = self._client.chat.completions.create(
                model=settings.llm.model,
                messages=msg_dicts,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        try:
            return await with_retry(
                asyncio.to_thread, _sync_call,
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
            loop = asyncio.get_running_loop()
            q: asyncio.Queue = asyncio.Queue()

            def _producer():
                try:
                    stream = self._client.chat.completions.create(
                        model=settings.llm.model,
                        messages=msg_dicts,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True,
                        timeout=60.0,
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            loop.call_soon_threadsafe(q.put_nowait, delta.content)
                except Exception as e:
                    loop.call_soon_threadsafe(q.put_nowait, e)
                finally:
                    loop.call_soon_threadsafe(q.put_nowait, None)

            threading.Thread(target=_producer, daemon=True).start()

            stream_error = None
            while True:
                token = await q.get()
                if token is None:
                    break
                if isinstance(token, Exception):
                    stream_error = token
                    break
                yield token

            # P2-3: 流式重试 — 可重试错误时重建 stream
            if stream_error is not None:
                from src.generation.llm.resilience import _is_retryable
                if attempt < max_retries and _is_retryable(stream_error):
                    delay = 1.0 * (backoff ** attempt)
                    logger.warning(f"stream_retry attempt={attempt + 1}/{max_retries} delay={delay:.1f}s error={stream_error}")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"llm_stream_failed error={stream_error}")
                raise stream_error
            return  # success — no error

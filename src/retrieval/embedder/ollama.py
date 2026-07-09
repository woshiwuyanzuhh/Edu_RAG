"""
Ollama Embedding — 通过 OpenAI 兼容 API 调用 Ollama BGE-M3。

解决问题 #15: embed() 接口接受 list[str]，一次批量发送。
"""
import asyncio
import hashlib
import logging
from openai import OpenAI

from src.interfaces.embedder import IEmbedder
from src.shared.config import settings
from src.shared.cache import cache_strategy

logger = logging.getLogger(__name__)


class OllamaEmbedder(IEmbedder):
    """Ollama BGE-M3 Embedding（via OpenAI 兼容 API）。"""

    def __init__(self):
        self._client: OpenAI | None = None
        self._dimension: int = 1024  # bge-m3 默认 1024 维

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.embedding.api_key.get_secret_value(),
                base_url=settings.embedding.api_base_url,
            )
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # P2-10: 批量大小控制 — 超过 batch_size 时分批发 API 请求
        batch_size = 32
        if len(texts) <= batch_size:
            return await self._embed_batch(texts)

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """单批 Embedding API 调用（带缓存）。"""
        # 1. 查缓存 (L1 进程 + L2 Redis)
        cache_key = f"edu_rag:emb:{hashlib.sha256('|'.join(texts).encode()).hexdigest()[:16]}"
        cached = await cache_strategy.get(cache_key)
        if cached is not None:
            logger.debug(f"ollama_embed_cache_hit count={len(texts)}")
            return cached

        # 2. API 调用
        client = self._get_client()

        def _sync_call():
            response = client.embeddings.create(
                model=settings.embedding.model,
                input=texts,
            )
            return [item.embedding for item in response.data]

        try:
            embeddings = await asyncio.to_thread(_sync_call)
            logger.debug(f"ollama_embed count={len(texts)} dim={len(embeddings[0]) if embeddings else 0}")
        except Exception as e:
            logger.error(f"ollama_embed_failed error={e}")
            raise

        # 3. 写缓存 (TTL=600s)
        await cache_strategy.set(cache_key, embeddings, ttl=600)
        return embeddings

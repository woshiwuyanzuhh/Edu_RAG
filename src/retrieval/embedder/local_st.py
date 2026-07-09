"""
本地 Sentence-Transformers Embedding。
"""
import asyncio
import logging
from sentence_transformers import SentenceTransformer

from src.interfaces.embedder import IEmbedder
from src.shared.config import settings

logger = logging.getLogger(__name__)


class LocalSTEmbedder(IEmbedder):
    """本地 sentence-transformers 模型。"""

    def __init__(self):
        self._model: SentenceTransformer | None = None

    @property
    def dimension(self) -> int:
        model = self._get_model()
        return model.get_sentence_embedding_dimension()

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"loading_local_embedding_model model={settings.embedding.local_model}")
            self._model = SentenceTransformer(settings.embedding.local_model)
            logger.info("local_embedding_model_loaded")
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()

        def _encode():
            return model.encode(texts, normalize_embeddings=True).tolist()

        return await asyncio.to_thread(_encode)

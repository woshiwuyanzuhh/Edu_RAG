"""Embedding 实现 — 延迟导入避免强制依赖。"""
from src.retrieval.embedder.ollama import OllamaEmbedder
from src.shared.config import settings

_default_embedder = None


def get_embedder() -> "IEmbedder":
    """获取当前配置的 embedder 实例（延迟导入）。"""
    global _default_embedder
    if _default_embedder is None:
        if settings.embedding.provider == "local":
            from src.retrieval.embedder.local_st import LocalSTEmbedder
            _default_embedder = LocalSTEmbedder()
        else:
            _default_embedder = OllamaEmbedder()
    return _default_embedder


__all__ = ["OllamaEmbedder", "get_embedder"]

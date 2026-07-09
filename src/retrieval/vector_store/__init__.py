"""向量数据库实现。

变更 (P0-6): 改为懒加载模式 — 首次调用 get_vector_store() 时才实例化，
避免 import-time 副作用（如 ChromaDB 路径不存在导致 import 即崩溃）。
"""
from src.shared.config import settings

# 全局单例（懒加载）
_default_store = None


def get_vector_store() -> "IVectorStore":
    """获取当前配置的向量库实例（懒加载）。"""
    global _default_store
    if _default_store is None:
        if settings.vector_store.provider == "milvus":
            from src.retrieval.vector_store.milvus import MilvusStore
            _default_store = MilvusStore()
        else:
            from src.retrieval.vector_store.chroma import ChromaStore
            _default_store = ChromaStore()
    return _default_store


__all__ = ["get_vector_store"]

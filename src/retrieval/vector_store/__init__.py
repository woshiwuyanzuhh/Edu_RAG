"""向量数据库实现 — Milvus（生产级分布式向量检索）。

懒加载模式：首次调用 get_vector_store() 时才实例化，
避免 import-time 副作用（如 Milvus 未启动导致 import 即崩溃）。
"""

# 全局单例（懒加载）
_default_store = None


def get_vector_store() -> "IVectorStore":
    """获取向量库实例（懒加载）。

    返回 MilvusStore，需 Milvus 服务运行中。
    """
    global _default_store
    if _default_store is None:
        from src.retrieval.vector_store.milvus import MilvusStore

        _default_store = MilvusStore()
    return _default_store


__all__ = ["get_vector_store"]

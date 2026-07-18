"""服务容器 — 依赖注入的全局服务单例。

解决问题：原则 #2 — 各层通过 Facade 接口通信。Orchestration 层不再直接
import ingress/retrieval/generation 内部模块。

所有服务实例在此处惰性创建，确保 settings 在实例化前已加载。
"""
from src.interfaces.ingestion_service import IIngestionService
from src.interfaces.generation_service import IGenerationService
from src.interfaces.retrieval_service import IRetrievalService

# 全局单例（惰性初始化）
_ingestion_svc: IIngestionService | None = None
_generation_svc: IGenerationService | None = None
_retrieval_svc: IRetrievalService | None = None


def get_ingestion_service() -> IIngestionService:
    """获取 Ingestion 服务单例。"""
    global _ingestion_svc
    if _ingestion_svc is None:
        from src.ingress import IngestionService
        from src.retrieval.embedder import get_embedder
        from src.retrieval.vector_store import get_vector_store
        _ingestion_svc = IngestionService(
            embedder=get_embedder(),
            vector_store=get_vector_store(),
        )
    return _ingestion_svc


def get_generation_service() -> IGenerationService:
    """获取 Generation 服务单例。"""
    global _generation_svc, _retrieval_svc
    if _generation_svc is None:
        from src.generation import GenerationService
        from src.providers.llm import OpenAICompatClient
        _retrieval_svc = get_retrieval_service()
        _generation_svc = GenerationService(
            llm_client=OpenAICompatClient(),
            retrieval_svc=_retrieval_svc,
        )
    return _generation_svc


def get_retrieval_service() -> IRetrievalService:
    """获取 Retrieval 服务单例。"""
    global _retrieval_svc
    if _retrieval_svc is None:
        from src.retrieval.service import RetrievalService
        from src.retrieval.embedder import get_embedder
        from src.retrieval.vector_store import get_vector_store
        from src.providers.llm import OpenAICompatClient
        _retrieval_svc = RetrievalService(
            embedder=get_embedder(),
            vector_store=get_vector_store(),
            llm_client=OpenAICompatClient(),
        )
    return _retrieval_svc

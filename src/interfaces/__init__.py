"""
全局抽象接口 — 所有外部依赖面向接口编程。

原则: 层内自治，层间契约。上层不感知下层实现细节。
"""
from src.interfaces.parser import IParser
from src.interfaces.chunker import IChunker
from src.interfaces.cleaner import ICleaner
from src.interfaces.embedder import IEmbedder
from src.interfaces.vector_store import IVectorStore, VectorItem, SearchResult, Chunk
from src.interfaces.llm import ILLMClient, Message
from src.interfaces.reranker import IReranker
from src.interfaces.query_expander import IQueryExpander
from src.interfaces.retrieval_service import IRetrievalService
from src.interfaces.ingestion_service import IIngestionService, IngestionResult
from src.interfaces.generation_service import IGenerationService
from src.interfaces.context_processor import IContextProcessor
from src.interfaces.guardrail import IGuardrail, GuardResult

__all__ = [
    "IParser",
    "IChunker",
    "ICleaner",
    "IEmbedder",
    "IVectorStore",
    "VectorItem",
    "SearchResult",
    "Chunk",
    "ILLMClient",
    "Message",
    "IReranker",
    "IQueryExpander",
    "IRetrievalService",
    "IIngestionService",
    "IngestionResult",
    "IGenerationService",
    "IContextProcessor",
    "IGuardrail",
    "GuardResult",
]

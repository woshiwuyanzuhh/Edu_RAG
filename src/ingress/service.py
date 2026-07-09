"""Ingestion 服务门面 — Ingress 层唯一对外入口。

封装完整写入管线：parse → clean → chunk → filter → embed → vector_insert → bm25_build

解决问题：原则 #2 — Orchestration 层通过此门面调用，不再直接 import ingress 内部模块。
"""
import logging
from pathlib import Path

from src.interfaces.ingestion_service import IIngestionService, IngestionResult
from src.interfaces.embedder import IEmbedder
from src.interfaces.vector_store import IVectorStore, VectorItem
from src.ingress.pipeline import run_ingestion, IngestionResult as PipelineResult
from src.ingress.parsers import PARSER_REGISTRY
from src.ingress.cleaners import CLEANER_REGISTRY
from src.ingress.chunkers import RecursiveChunker
from src.shared.exceptions import UnsupportedFileType, EmptyDocumentError
from src.retrieval.keyword import build_bm25 as build_shared_bm25
from src.shared.cache import cache_strategy

logger = logging.getLogger(__name__)


class IngestionService(IIngestionService):
    """Ingestion 服务实现 — 依赖注入 Embedder + VectorStore。"""

    def __init__(self, embedder: IEmbedder, vector_store: IVectorStore):
        self._embedder = embedder
        self._vector_store = vector_store

    async def ingest(
        self,
        file_path: str,
        doc_id: int,
        kb_id: int,
        *,
        doc_type: str = "general",
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ) -> IngestionResult:
        logger.info(f"ingestion_start file={file_path} doc_id={doc_id} kb_id={kb_id} doc_type={doc_type}")

        # 1. 校验文件类型
        ext = Path(file_path).suffix.lower()
        if ext not in PARSER_REGISTRY:
            raise UnsupportedFileType(f"不支持的文件类型: {ext}，支持: {list(PARSER_REGISTRY.keys())}")

        # 2. 执行写入管线（parse → clean → chunk → filter）
        pipeline_result: PipelineResult = await run_ingestion(
            file_path=file_path, doc_id=doc_id, kb_id=kb_id,
            doc_type=doc_type, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        )

        if not pipeline_result.chunks:
            raise EmptyDocumentError("文档解析后无有效内容")

        # 3. Embedding + 向量库写入
        chunk_texts = [c.text for c in pipeline_result.chunks]
        embeddings = await self._embedder.embed(chunk_texts)

        items = [
            VectorItem(
                id=f"{doc_id}_{c.chunk_index}",
                text=c.text,
                embedding=embeddings[i],
                metadata={
                    "doc_id": doc_id,
                    "chunk_index": c.chunk_index,
                    "knowledge_base_id": kb_id,
                    "source_file": c.source_file,
                    "doc_type": doc_type,
                },
            )
            for i, c in enumerate(pipeline_result.chunks)
        ]
        await self._vector_store.insert(items)

        # 4. 构建 BM25 索引
        try:
            build_shared_bm25(chunk_texts)
            logger.info(f"bm25_built kb_id={kb_id} doc_id={doc_id} chunks={len(chunk_texts)}")
        except Exception as e:
            logger.warning(f"bm25_build_failed error={e}")

        # 5. 失效缓存
        await cache_strategy.invalidate(f"edu_rag:*:{kb_id}:*")

        logger.info(f"ingestion_complete doc_id={doc_id} chunks={len(chunk_texts)}")
        return IngestionResult(
            chunks=[{"text": c.text, "chunk_index": c.chunk_index, "metadata": c.metadata}
                    for c in pipeline_result.chunks],
            total_chars=pipeline_result.total_chars,
            original_chars=pipeline_result.original_chars,
            chunk_count=len(pipeline_result.chunks),
            stats=pipeline_result.stats,
        )

    async def delete_document(self, doc_id: int, kb_id: int, file_path: str) -> None:
        """删除文档向量 + 物理文件 + 失效缓存。

        P0-7: 使用 delete_by_filter 按 doc_id 精确删除，不再硬编码 range(1000)。
        """
        import os

        # 删除向量 — 按 metadata.doc_id 过滤，精确删除
        try:
            await self._vector_store.delete_by_filter({"doc_id": str(doc_id)})
        except Exception as e:
            # ChromaDB 可能不支持 delete_by_filter，fallback 到 ID 范围删除
            logger.warning(f"vector_delete_by_filter_failed doc_id={doc_id} error={e} — trying delete_by_ids")
            try:
                # 分 10 批，每批 1000 个，覆盖最多 10000 chunks
                for batch_start in range(0, 10000, 1000):
                    ids = [f"{doc_id}_{i}" for i in range(batch_start, batch_start + 1000)]
                    await self._vector_store.delete_by_ids(ids)
            except Exception as e2:
                logger.warning(f"vector_delete_final_failed doc_id={doc_id} error={e2}")

        # 删除物理文件
        if os.path.exists(file_path):
            os.remove(file_path)

        # 失效缓存
        await cache_strategy.invalidate(f"edu_rag:*:{kb_id}:*")
        logger.info(f"document_deleted doc_id={doc_id} kb_id={kb_id}")

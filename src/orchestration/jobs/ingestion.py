"""Document ingestion orchestration job.

This module keeps API handlers thin and gives future queue workers a stable
entry point for document processing.
"""
import os
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.orchestration.services import get_ingestion_service
from src.shared.config import settings
from src.shared.models.orm import Document

logger = logging.getLogger(__name__)


async def process_document_ingestion(
    *,
    db: AsyncSession,
    document: Document,
    knowledge_base_id: int,
    doc_type: str,
) -> int:
    """Run ingestion for a document and persist its final status."""
    ingestion_svc = get_ingestion_service()
    try:
        result = await ingestion_svc.ingest(
            file_path=document.file_path,
            doc_id=document.id,
            kb_id=knowledge_base_id,
            doc_type=doc_type,
            chunk_size=settings.ingress_cfg.chunk_size,
            chunk_overlap=settings.ingress_cfg.chunk_overlap,
        )

        document.chunk_count = result.chunk_count
        document.status = "done"
        document.error_message = None
        await db.commit()
        return result.chunk_count
    except Exception as e:
        document.status = "error"
        document.error_message = str(e)
        await db.commit()
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        raise


async def delete_document_resources(*, doc_id: int, kb_id: int, file_path: str) -> None:
    """Delete vector-store entries, physical file, and related cache entries."""
    try:
        ingestion_svc = get_ingestion_service()
        await ingestion_svc.delete_document(doc_id=doc_id, kb_id=kb_id, file_path=file_path)
    except Exception:
        logger.warning(f"ingestion_delete_failed doc_id={doc_id}")

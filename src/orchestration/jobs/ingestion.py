"""Document ingestion orchestration job.

This module keeps API handlers thin and gives future queue workers a stable
entry point for document processing.
"""

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from src.orchestration.services import get_ingestion_service
from src.shared.config import settings
from src.shared.models.orm import Document

logger = logging.getLogger(__name__)


def _quarantine_failed_file(file_path: str) -> None:
    """入库失败时把原文件重命名为 .failed 后缀，便于诊断与重试。

    相比直接删除，这种做法的好处：
    1. 用户/管理员可下载原文件，本地修复（如解密 PDF）后重新上传
    2. 排查问题时无需让用户再次上传
    3. .failed 后缀避免被 ingestion 误识别为有效文件
    """
    if not file_path or not os.path.exists(file_path):
        return
    failed_path = f"{file_path}.failed"
    try:
        os.rename(file_path, failed_path)
        logger.info(f"file_quarantined original={file_path} -> {failed_path}")
    except OSError as e:
        # 重命名失败（跨设备/权限）→ 兜底删除
        logger.warning(f"quarantine_failed, fallback to remove: {e}")
        try:
            os.remove(file_path)
        except OSError:
            pass


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
        # 失败时保留文件用于诊断：重命名为 .failed 后缀而不是删除
        # 用户可以下载原文件、修复后重新上传；管理员也可基于 .failed 文件排查问题
        _quarantine_failed_file(document.file_path)
        raise


async def delete_document_resources(*, doc_id: int, kb_id: int, file_path: str) -> None:
    """Delete vector-store entries, physical file, and related cache entries."""
    try:
        ingestion_svc = get_ingestion_service()
        await ingestion_svc.delete_document(doc_id=doc_id, kb_id=kb_id, file_path=file_path)
    except Exception:
        logger.warning(f"ingestion_delete_failed doc_id={doc_id}")

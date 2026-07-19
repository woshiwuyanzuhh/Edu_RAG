"""ARQ worker 任务定义（P1-C5）。

任务在独立 worker 进程执行，与 API 进程隔离：
- 避免文档解析/向量化阻塞 API 请求
- 单 worker 串行处理消除多 app worker 下的 BM25 写竞争
"""

import logging
import os

logger = logging.getLogger(__name__)


async def process_document_ingestion_task(
    ctx: dict,
    *,
    doc_id: int,
    kb_id: int,
    doc_type: str,
) -> None:
    """异步文档入库任务。

    在独立 worker 进程执行。独立开 db session，调用 ingestion service，
    更新 Document 状态。失败时清理物理文件并重试（由 ARQ max_tries 控制）。
    """
    from src.orchestration.services import get_ingestion_service
    from src.shared.config import settings
    from src.shared.database.mysql import _session_factory
    from src.shared.models.orm import Document

    if _session_factory is None:
        raise RuntimeError("MySQL 未初始化，worker 无法处理任务")

    logger.info(f"ingestion_task_start doc_id={doc_id} kb_id={kb_id} doc_type={doc_type}")

    async with _session_factory() as db:
        doc = await db.get(Document, doc_id)
        if doc is None:
            logger.warning(f"ingestion_task doc_not_found doc_id={doc_id}")
            return

        try:
            ingestion_svc = get_ingestion_service()
            result = await ingestion_svc.ingest(
                file_path=doc.file_path,
                doc_id=doc.id,
                kb_id=kb_id,
                doc_type=doc_type,
                chunk_size=settings.ingress_cfg.chunk_size,
                chunk_overlap=settings.ingress_cfg.chunk_overlap,
            )
            doc.chunk_count = result.chunk_count
            doc.status = "done"
            doc.error_message = None
            await db.commit()
            logger.info(f"ingestion_task_done doc_id={doc_id} chunks={result.chunk_count}")
        except Exception as e:
            doc.status = "error"
            doc.error_message = str(e)
            await db.commit()
            # 清理物理文件（与同步路径行为一致）
            if os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except OSError:
                    pass
            logger.error(f"ingestion_task_failed doc_id={doc_id} error={e}")
            raise  # ARQ 会按 max_tries 重试

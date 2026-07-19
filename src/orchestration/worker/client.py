"""ARQ 客户端 — 任务投递 + 同步兜底（P1-C5）。

API 进程通过 enqueue_ingestion 投递任务；投递失败时调用方回退同步处理，
保证开发环境（未启动 worker）也能正常工作。
"""

import logging

logger = logging.getLogger(__name__)

_pool = None


async def _get_arq_pool():
    """获取 ARQ 连接池（懒加载，进程级单例）。"""
    global _pool
    if _pool is None:
        from arq import create_pool
        from arq.connections import RedisSettings

        from src.shared.config import settings

        pwd = settings.redis.password.get_secret_value()
        _pool = await create_pool(
            RedisSettings(
                host=settings.redis.host,
                port=settings.redis.port,
                password=pwd or None,
                database=settings.redis.db,
            )
        )
    return _pool


async def enqueue_ingestion(*, doc_id: int, kb_id: int, doc_type: str) -> bool:
    """投递文档入库任务到 ARQ 队列。

    Returns:
        True = 投递成功；False = 投递失败，调用方应回退同步处理。
    """
    try:
        pool = await _get_arq_pool()
        await pool.enqueue_job(
            "process_document_ingestion_task",
            doc_id=doc_id,
            kb_id=kb_id,
            doc_type=doc_type,
        )
        logger.info(f"ingestion_enqueued doc_id={doc_id}")
        return True
    except Exception as e:
        logger.warning(f"arq_enqueue_failed doc_id={doc_id} error={e} — 回退同步")
        return False


async def close_arq_pool() -> None:
    """关闭 ARQ 连接池（应用关闭时调用）。"""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            pass
        _pool = None

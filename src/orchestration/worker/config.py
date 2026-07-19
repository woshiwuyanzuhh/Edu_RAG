"""ARQ Worker 配置（P1-C5）。

启动 worker:
    arq src.orchestration.worker.config.WorkerSettings

生产部署见 docker/docker-compose.yml 的 worker 服务。

注意（审查修复）：worker 是独立进程，不执行 app lifespan，
必须在 on_startup 中自行初始化 MySQL/Redis/向量库/BM25，否则任务无法执行。
"""

import logging

from arq.connections import RedisSettings

from src.orchestration.worker.tasks import process_document_ingestion_task
from src.shared.config import settings

logger = logging.getLogger(__name__)


async def on_startup(ctx: dict) -> None:
    """worker 启动：初始化 MySQL/Redis/向量库/BM25（与 app lifespan 对齐）。

    worker 独立进程不执行 app lifespan，必须在此初始化所有依赖，
    否则 _session_factory 为 None，任务抛 RuntimeError。
    """
    from src.retrieval.keyword import load_all_bm25_from_db
    from src.retrieval.vector_store import get_vector_store
    from src.shared.cache import set_redis_client
    from src.shared.database.mysql import init_mysql
    from src.shared.database.redis import redis_client

    await init_mysql()
    if await redis_client.connect():
        set_redis_client(redis_client)
    else:
        logger.warning("worker_redis_unavailable — 缓存降级")
    vs = get_vector_store()
    await vs.connect()
    bm25_count = await load_all_bm25_from_db()
    logger.info(f"worker_started bm25_loaded={bm25_count}")


async def on_shutdown(ctx: dict) -> None:
    """worker 关闭：释放连接。"""
    from src.retrieval.vector_store import get_vector_store
    from src.shared.database.mysql import close_mysql
    from src.shared.database.redis import redis_client

    try:
        await get_vector_store().disconnect()
    except Exception:
        pass
    await redis_client.disconnect()
    await close_mysql()
    logger.info("worker_stopped")


class WorkerSettings:
    """ARQ worker 配置。

    - on_startup/on_shutdown: 初始化/释放连接（worker 独立进程必需）
    - max_jobs: 单 worker 并发任务数（文档解析 CPU/内存密集，保守设置）
    - job_timeout: 单任务超时（大 PDF 解析可能较慢）
    - max_tries: 失败重试次数（含首次，3 = 1 次执行 + 2 次重试）
    """

    functions = [process_document_ingestion_task]
    redis_settings = RedisSettings(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password.get_secret_value() or None,
        database=settings.redis.db,
    )
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 10
    job_timeout = 600  # 10 分钟
    max_tries = 3

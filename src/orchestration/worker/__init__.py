"""ARQ 异步任务队列（P1-C5）。

文档入库等重型任务通过 ARQ + Redis broker 异步执行，避免阻塞 API 请求，
并解决多 app worker 下的 BM25 写竞争（文档解析/索引构建集中在独立 worker
进程串行处理，单写无竞争）。

启动 worker:
    arq src.orchestration.worker.config.WorkerSettings

配置:
    APP__ASYNC_INGESTION=true 时，API 投递任务到队列；false 时同步执行（开发模式）。
"""

from src.orchestration.worker.client import close_arq_pool, enqueue_ingestion

__all__ = ["enqueue_ingestion", "close_arq_pool"]

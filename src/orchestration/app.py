"""
FastAPI 应用入口 — 四层 RAG 架构的编排中心。

生命周期:
    启动: config validate → logging → MySQL → Redis → ChromaDB → cache
    运行: 中间件链 → API 路由
    关闭: ChromaDB disconnect → Redis disconnect → MySQL close

中间件链（Phase 3）:
    RequestID → Auth → RateLimit → CORS → ErrorHandler
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio

# Windows UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, FileResponse

from src.shared.config import settings, PROJECT_ROOT
from src.shared.logging_config import setup_logging, get_logger
from src.shared.security import validate_secrets, print_security_warnings
from src.shared.cache import set_redis_client
from src.shared.database.mysql import init_mysql, close_mysql
from src.shared.database.redis import redis_client
from src.retrieval.vector_store import get_vector_store
from src.orchestration.middleware import AuthMiddleware, RequestIDMiddleware, TimeoutMiddleware, register_error_handlers
from src.orchestration.middleware.rate_limit import RateLimitMiddleware

logger = get_logger(__name__)

# 最大请求体大小 (MB) — P1-7: 与 max_upload_size_mb 统一，避免上传 50MB 但 body 限制 10MB 的矛盾
MAX_BODY_MB = settings.app.max_upload_size_mb


# ======================== 生命周期 ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭资源管理。"""

    # ── 启动阶段 ──
    logger.info("=" * 50)
    logger.info("  edu_rag v2.0 启动中...")
    logger.info("=" * 50)

    # 0. 初始化日志
    setup_logging(debug=settings.app.debug)
    logger.info("logging_initialized")

    # 1. 安全配置校验 (解决问题 #6, #7)
    warnings = validate_secrets(settings)
    print_security_warnings(warnings)

    # 2. MySQL
    logger.info(f"connecting_mysql host={settings.mysql.host} port={settings.mysql.port}")
    try:
        await init_mysql()
        logger.info("mysql_connected")
    except Exception as e:
        logger.critical(f"mysql_failed error={e}")
        raise  # MySQL 是关键服务，失败则阻止启动

    # 3. Redis
    logger.info(f"connecting_redis host={settings.redis.host} port={settings.redis.port}")
    redis_ok = await redis_client.connect()
    if redis_ok:
        set_redis_client(redis_client)
    else:
        logger.warning("redis_unavailable — 缓存功能不可用，系统降级运行")

    # 4. ChromaDB
    logger.info(f"connecting_vector_store provider={settings.vector_store.provider}")
    try:
        vector_store = get_vector_store()
        await vector_store.connect()
        count = await vector_store.count()
        logger.info(f"vector_store_connected count={count}")
    except Exception as e:
        logger.warning(f"vector_store_failed error={e} — 向量检索不可用")

    # 5. BM25 索引加载（P0-C3: 从 MySQL 恢复，避免崩溃后混合检索静默失效）
    try:
        from src.retrieval.keyword import load_all_bm25_from_db
        bm25_count = await load_all_bm25_from_db()
        logger.info(f"bm25_restored count={bm25_count}")
    except Exception as e:
        logger.warning(f"bm25_load_failed error={e} — BM25 将在首次写入时重建")

    logger.info(f"edu_rag_started host={settings.app.host} port={settings.app.port}")

    yield

    # ── 关闭阶段 ──
    logger.info("edu_rag_shutting_down")
    try:
        await get_vector_store().disconnect()
    except Exception:
        pass
    await redis_client.disconnect()
    await close_mysql()
    logger.info("edu_rag_stopped")


# ======================== 应用实例 ========================

app = FastAPI(
    title="edu_rag v2.0 - 智能题库系统",
    description="基于四层 RAG 架构的教育智能题库：Ingestion → Retrieval → Generation → Orchestration",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)

# ── 中间件注册（顺序重要）──
app.add_middleware(RequestIDMiddleware)   # 1. 先注入 request_id
app.add_middleware(AuthMiddleware)        # 2. 再鉴权
app.add_middleware(TimeoutMiddleware)     # 3. 超时保护（SSE 豁免）
app.add_middleware(RateLimitMiddleware)   # 4. 限流（P2-8）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_credentials=True,
    # P2-10: 收紧 CORS 方法与头，避免全放行
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-Request-ID"],
)

# ── 请求体大小限制 ──
from fastapi import Request as FastAPIRequest
@app.middleware("http")
async def limit_body_size(request: FastAPIRequest, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        max_bytes = MAX_BODY_MB * 1024 * 1024
        if int(content_length) > max_bytes:
            from fastapi.responses import ORJSONResponse as _ORJ
            return _ORJ(
                status_code=413,
                content={"success": False, "message": f"请求体超过 {MAX_BODY_MB}MB 限制", "data": None},
            )
    return await call_next(request)

# ── 异常处理 ──
register_error_handlers(app)

# ── API 路由 ──
from src.orchestration.api.knowledge import router as kb_router
from src.orchestration.api.documents import router as docs_router
from src.orchestration.api.qa import router as qa_router
from src.orchestration.api.exam import router as exam_router

app.include_router(kb_router)
app.include_router(docs_router)
app.include_router(qa_router)
app.include_router(exam_router)

# ── 健康检查 ──

@app.get("/health")
async def health_check():
    """P0-C8: 探活依赖（MySQL+Redis+向量库），任一失败返回 503，供容灾 LB 健康检查。"""
    checks = {"mysql": False, "redis": False, "vector_store": False}

    # MySQL
    try:
        from src.shared.database.mysql import _session_factory
        from sqlalchemy import text as _sql_text
        if _session_factory is not None:
            async with _session_factory() as session:
                await session.execute(_sql_text("SELECT 1"))
            checks["mysql"] = True
    except Exception:
        pass

    # Redis
    try:
        if redis_client.is_connected:
            await redis_client.client.ping()
            checks["redis"] = True
    except Exception:
        pass

    # 向量库（ChromaDB/Milvus 通用：count() 可达即健康，3s 超时保护）
    try:
        vs = get_vector_store()
        await asyncio.wait_for(vs.count(), timeout=3.0)
        checks["vector_store"] = True
    except Exception:
        pass

    all_ok = all(checks.values())
    return ORJSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ok" if all_ok else "degraded",
            "service": "edu_rag",
            "version": "2.0.0",
            "checks": checks,
        },
    )


# ── Prometheus 指标（P2-2）──

def _setup_prometheus():
    """尝试注册 Prometheus 指标端点（可选依赖）。P2-C10: 含业务指标。"""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        # P2-C10: 注册业务指标（Counter/Histogram/Gauge 定义即注册到全局 REGISTRY）
        from src.orchestration.middleware import metrics  # noqa: F401
        instrumentator = Instrumentator()
        instrumentator.instrument(app)
        instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)
        logger.info("prometheus_metrics_enabled endpoint=/metrics (含业务指标)")
    except ImportError:
        logger.info("prometheus_fastapi_instrumentator 未安装，/metrics 不可用")

_setup_prometheus()


# ── SPA 前端静态文件（生产模式）──

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
# P3-4: SPA catch-all 排除 API/Health/Metrics 路径
API_PATH_PREFIXES = ("/api", "/health", "/metrics", "/docs", "/openapi.json", "/redoc")

if FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend_assets")

    @app.get("/")
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str = ""):
        # 排除 API 和监控路径（P3-4）
        if full_path and any(full_path.startswith(p.lstrip("/")) for p in API_PATH_PREFIXES):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"success": False, "message": "Not Found"})
        file_path = FRONTEND_DIST / full_path if full_path else FRONTEND_DIST / "index.html"
        # P2-8: 路径遍历校验 — resolve() 后断言仍在 FRONTEND_DIST 内
        try:
            resolved = file_path.resolve()
            if not str(resolved).startswith(str(FRONTEND_DIST.resolve())):
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=404, content={"success": False, "message": "Not Found"})
        except Exception:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"success": False, "message": "Not Found"})
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")


# ======================== 直接运行 ========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.orchestration.app:app", host=settings.app.host, port=settings.app.port, reload=True)


def main():
    """CLI 入口 — 供 pyproject.toml 的 [project.scripts] 使用。"""
    import uvicorn
    uvicorn.run("src.orchestration.app:app", host=settings.app.host, port=settings.app.port)

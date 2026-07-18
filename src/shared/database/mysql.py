"""异步 MySQL 客户端 — SQLAlchemy 2.0 async。

变更 (Phase 3 P2-9): 优先使用 Alembic 迁移，fallback create_all。
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.shared.config import settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory: async_sessionmaker | None = None


async def init_mysql() -> None:
    """初始化异步 MySQL 引擎 + 会话工厂。

    数据库迁移策略：
        1. 优先运行 alembic upgrade head（如果可用）
        2. fallback 到 Base.metadata.create_all（开发模式）
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.mysql.url,
        pool_size=settings.mysql.pool_size,
        max_overflow=settings.mysql.max_overflow,
        pool_recycle=settings.mysql.pool_recycle,
        pool_pre_ping=settings.mysql.pool_pre_ping,
        echo=False,
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # P2-9: 优先 Alembic 迁移
    try:
        from alembic.config import Config
        from alembic import command
        from pathlib import Path

        alembic_ini = Path(__file__).resolve().parent.parent.parent.parent / "alembic.ini"
        if alembic_ini.exists():
            alembic_cfg = Config(str(alembic_ini))
            # 覆盖 DB URL（由 env.py 从 settings 读取）
            command.upgrade(alembic_cfg, "head")
            logger.info("alembic_upgrade_complete")
            return
    except Exception as e:
        logger.warning(f"alembic_upgrade_failed error={e} — falling back to create_all")

    # Fallback: 自动建表
    from src.shared.models.orm import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("mysql_create_all_complete (fallback)")


async def get_db() -> AsyncSession:
    """FastAPI 依赖：获取异步数据库会话。"""
    if _session_factory is None:
        raise RuntimeError("MySQL 未初始化，请先调用 init_mysql()")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_mysql() -> None:
    """关闭 MySQL 连接池。"""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None

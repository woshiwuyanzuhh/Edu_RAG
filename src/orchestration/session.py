"""
对话会话管理 — 多轮问答支持。

解决问题 #14: 无对话历史，无法多轮问答。

存储策略:
    - Redis: 热数据（最近活跃会话），TTL 30min
    - MySQL: 持久化（ChatSession 表）
"""
import uuid
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.redis import redis_client
from src.shared.models.orm import ChatSession

logger = logging.getLogger(__name__)

SESSION_TTL = 1800  # Redis 中会话 TTL: 30 分钟


class SessionManager:
    """对话会话管理器。"""

    def __init__(self):
        self._redis = redis_client

    async def create_session(
        self,
        db: AsyncSession,
        knowledge_base_id: int | None = None,
    ) -> str:
        """创建新会话。"""
        session_key = uuid.uuid4().hex[:16]

        # 持久化到 MySQL
        session = ChatSession(session_key=session_key, knowledge_base_id=knowledge_base_id, messages=[])
        db.add(session)
        await db.commit()

        # 缓存到 Redis
        await self._redis.set_json(f"session:{session_key}", {"messages": [], "kb_id": knowledge_base_id}, ttl=SESSION_TTL)

        logger.info(f"session_created session_key={session_key}")
        return session_key

    async def get_session(self, session_key: str, db: AsyncSession) -> dict | None:
        """获取会话数据（先查 Redis，再查 MySQL）。"""
        # L1: Redis
        cached = await self._redis.get_json(f"session:{session_key}")
        if cached:
            return cached

        # L2: MySQL
        result = await db.execute(select(ChatSession).where(ChatSession.session_key == session_key))
        session = result.scalar_one_or_none()
        if session:
            data = {"messages": session.messages or [], "kb_id": session.knowledge_base_id}
            await self._redis.set_json(f"session:{session_key}", data, ttl=SESSION_TTL)
            return data

        return None

    async def append_message(self, session_key: str, role: str, content: str, db: AsyncSession) -> None:
        """向会话追加一条消息。"""
        session_data = await self.get_session(session_key, db)
        if not session_data:
            return

        session_data["messages"].append({"role": role, "content": content})

        # 更新 Redis
        await self._redis.set_json(f"session:{session_key}", session_data, ttl=SESSION_TTL)

        # 更新 MySQL
        result = await db.execute(select(ChatSession).where(ChatSession.session_key == session_key))
        session = result.scalar_one_or_none()
        if session:
            session.messages = session_data["messages"]
            await db.commit()

    async def get_history(self, session_key: str, db: AsyncSession) -> list[dict]:
        """获取会话的对话历史。"""
        data = await self.get_session(session_key, db)
        return data.get("messages", []) if data else []


# 全局实例
session_manager = SessionManager()

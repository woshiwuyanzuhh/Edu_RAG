"""集成测试 — 数据库 + 缓存 + 组件连通性。

这些测试需要 MySQL/Redis 处于可用状态。如服务不可用，测试将自动跳过。
每个测试在独立的 asyncio.run() 中运行，自行调用 connect/init 管理状态。
"""
import pytest
import asyncio

# ── 服务可用性检查（使用同步客户端，避免事件循环问题）──

def _check_mysql():
    try:
        from src.shared.config import settings
        import pymysql
        conn = pymysql.connect(
            host=settings.mysql.host, port=settings.mysql.port,
            user=settings.mysql.user,
            password=settings.mysql.password.get_secret_value(),
            database=settings.mysql.database,
            connect_timeout=5,
        )
        conn.close()
        return True
    except Exception:
        return False


def _check_redis():
    try:
        from src.shared.config import settings
        import redis
        r = redis.Redis(
            host=settings.redis.host, port=settings.redis.port,
            db=settings.redis.db, socket_connect_timeout=5,
        )
        r.ping()
        r.close()
        return True
    except Exception:
        return False


MYSQL_OK = _check_mysql()
REDIS_OK = _check_redis()

requires_mysql = pytest.mark.skipif(not MYSQL_OK, reason="MySQL 不可用")
requires_redis = pytest.mark.skipif(not REDIS_OK, reason="Redis 不可用")
requires_services = pytest.mark.skipif(
    not (MYSQL_OK and REDIS_OK),
    reason="MySQL 或 Redis 不可用"
)


# ═══════════════════════════════════════════════
# Helpers — 每个测试独立管理连接
# ═══════════════════════════════════════════════

async def _fresh_mysql_session():
    """每次测试重新初始化 MySQL 并返回 session factory。"""
    import src.shared.database.mysql as mysql_mod
    # 强制重新初始化（确保 session factory 绑定到当前事件循环）
    if mysql_mod._engine is not None:
        await mysql_mod._engine.dispose()
        mysql_mod._engine = None
        mysql_mod._session_factory = None
    await mysql_mod.init_mysql()
    return mysql_mod._session_factory  # 返回 factory (async_sessionmaker)，不是 session


async def _fresh_redis_client():
    """每次测试重新连接 Redis（确保连接绑定到当前事件循环）。"""
    from src.shared.database.redis import redis_client
    # 断开旧连接（可能来自上一个事件循环）
    if redis_client._redis is not None:
        try:
            await redis_client._redis.close()
        except Exception:
            pass
        redis_client._redis = None
    ok = await redis_client.connect()
    if not ok:
        raise RuntimeError("Redis 连接失败")
    return redis_client


# ═══════════════════════════════════════════════
# 1. 数据库读写测试
# ═══════════════════════════════════════════════

class TestDatabaseCRUD:
    """MySQL 表 CRUD 验证。"""

    @requires_mysql
    def test_knowledge_base_crud(self):
        from src.shared.models.orm import KnowledgeBase
        from sqlalchemy import select

        async def _run():
            factory = await _fresh_mysql_session()
            async with factory() as s:
                kb = KnowledgeBase(name="_test_int_kb_", description="集成测试KB")
                s.add(kb)
                await s.commit()
                assert kb.id > 0

                result = await s.execute(
                    select(KnowledgeBase).where(KnowledgeBase.id == kb.id)
                )
                fetched = result.scalar_one()
                assert fetched.name == "_test_int_kb_"

                await s.delete(fetched)
                await s.commit()
            return True

        assert asyncio.run(_run())

    @requires_mysql
    def test_document_and_exam_cascade(self):
        from src.shared.models.orm import KnowledgeBase, Document, ExamRecord

        async def _run():
            factory = await _fresh_mysql_session()
            async with factory() as s:
                kb = KnowledgeBase(name="_test_int_full_", description="全流程")
                s.add(kb)
                await s.commit()

                doc = Document(
                    filename="test.pdf", file_path="/tmp/test.pdf",
                    file_type="pdf", file_size=1024,
                    knowledge_base_id=kb.id, chunk_count=3, status="done",
                )
                s.add(doc)

                record = ExamRecord(
                    knowledge_base_id=kb.id,
                    question_type="mixed", question_count=3, difficulty="medium",
                    questions=[{"number": 1}],
                    answers=[{"number": 1, "answer": "A"}],
                    scores=[{"number": 1, "score": 25}],
                    dimensions={"concept": 25, "analysis": 25, "memory": 25, "application": 25},
                    total_score=100, max_score=100, status="graded",
                )
                s.add(record)
                await s.commit()
                assert doc.id > 0
                assert record.id > 0
                assert record.dimensions["concept"] == 25

                # 级联清理
                await s.delete(kb)
                await s.commit()
            return True

        assert asyncio.run(_run())

    @requires_mysql
    def test_chat_session_crud(self):
        from src.shared.models.orm import ChatSession
        from sqlalchemy import select

        async def _run():
            factory = await _fresh_mysql_session()
            async with factory() as s:
                cs = ChatSession(session_key="_test_session_xyz", knowledge_base_id=None, messages=[])
                s.add(cs)
                await s.commit()
                assert cs.id > 0

                result = await s.execute(
                    select(ChatSession).where(ChatSession.session_key == "_test_session_xyz")
                )
                fetched = result.scalar_one()
                assert fetched.messages == []

                await s.delete(fetched)
                await s.commit()
            return True

        assert asyncio.run(_run())


# ═══════════════════════════════════════════════
# 2. 缓存集成测试
# ═══════════════════════════════════════════════

class TestRedisIntegration:
    """Redis 读写验证。"""

    @requires_redis
    def test_set_and_get(self):
        async def _run():
            rc = await _fresh_redis_client()
            ok = await rc.set("_test_int_k", "hello_redis", ex=60)
            assert ok is True
            val = await rc.get("_test_int_k")
            await rc.delete("_test_int_k")
            return val
        result = asyncio.run(_run())
        assert result == "hello_redis"

    @requires_redis
    def test_json_set_and_get(self):
        async def _run():
            rc = await _fresh_redis_client()
            ok = await rc.set_json("_test_int_j", {"msg": "hi", "n": 42}, ttl=60)
            assert ok is True
            val = await rc.get_json("_test_int_j")
            await rc.delete("_test_int_j")
            return val
        result = asyncio.run(_run())
        assert result == {"msg": "hi", "n": 42}

    @requires_redis
    def test_missing_key(self):
        async def _run():
            rc = await _fresh_redis_client()
            return await rc.get("_nonexistent_key_xyz_999")
        assert asyncio.run(_run()) is None


class TestCacheStrategyIntegration:
    """CacheStrategy L1+L2 集成。"""

    @requires_redis
    def test_set_get_invalidate(self):
        async def _run():
            rc = await _fresh_redis_client()
            from src.shared.cache import CacheStrategy, set_redis_client
            set_redis_client(rc)

            strategy = CacheStrategy()
            await strategy.set("_test_cs:key", {"status": "ok"}, ttl=60)
            val = await strategy.get("_test_cs:key")
            assert val == {"status": "ok"}

            await strategy.invalidate("_test_cs:*")
            val2 = await strategy.get("_test_cs:key")
            return val, val2

        val, val2 = asyncio.run(_run())
        assert val == {"status": "ok"}
        assert val2 is None


# ═══════════════════════════════════════════════
# 3. 组件连通性测试
# ═══════════════════════════════════════════════

class TestComponentConnectivity:
    """核心组件可正常实例化和连接。"""

    @requires_mysql
    def test_embedder_dimension(self):
        from src.retrieval.embedder import OllamaEmbedder
        e = OllamaEmbedder()
        assert e.dimension == 1024

    @requires_mysql
    def test_chroma_store_health(self):
        from src.retrieval.vector_store.chroma import ChromaStore

        async def _run():
            store = ChromaStore()
            await store.connect()
            count = await store.count()
            assert isinstance(count, int)
            return count
        count = asyncio.run(_run())
        assert count >= 0

    @requires_services
    def test_retrieval_service_di(self):
        from src.retrieval.service import RetrievalService
        from src.retrieval.embedder import OllamaEmbedder
        from src.retrieval.vector_store.chroma import ChromaStore

        svc = RetrievalService(embedder=OllamaEmbedder(), vector_store=ChromaStore())
        assert svc is not None
        assert svc._embedder is not None
        assert svc._vector_store is not None

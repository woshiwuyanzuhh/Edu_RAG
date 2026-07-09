"""pytest fixtures — mock 环境变量 + 全局状态清理。"""
import sys
import asyncio
from pathlib import Path

# 确保项目根在 Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_env():
    """确保不读取真实 .env，使用 v2 __ 嵌套格式。"""
    with patch.dict("os.environ", {
        "LLM__API_KEY": "sk-test-key-for-unit-tests",
        "MYSQL__PASSWORD": "test_pwd_123",
        "REDIS__PASSWORD": "",
        "APP__API_KEY": "",
    }):
        yield


@pytest.fixture(scope="session", autouse=True)
def _cleanup_global_state():
    """在所有测试完成后，重置 MySQL/Redis 全局状态。

    集成测试会在自己的 asyncio.run() 中创建 MySQL engine 和 Redis 连接，
    这些资源绑定到测试事件循环（已销毁），残留的全局引用会导致后续服务启动失败。
    """
    yield

    # 测试全部完成，清理全局状态
    try:
        import src.shared.database.mysql as mysql_mod
        if mysql_mod._engine is not None:
            try:
                asyncio.run(mysql_mod._engine.dispose())
            except Exception:
                pass
        mysql_mod._engine = None
        mysql_mod._session_factory = None
    except Exception:
        pass

    try:
        import src.shared.database.redis as redis_mod
        rc = redis_mod.redis_client
        if rc._redis is not None:
            try:
                asyncio.run(rc._redis.close())
            except Exception:
                pass
        rc._redis = None
    except Exception:
        pass

"""
结构化日志配置 — 基于 Python 标准 logging + JSON 格式输出。

原则 (来自系统架构设计准则 #8)：
    先建立端到端可观测性，再谈优化。
    没有可观测性的优化是盲目调参。

用法：
    from src.shared.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info(f"retrieval_complete query={query} hits={hit_count} latency={latency_ms}ms")
"""

import logging
import sys


def setup_logging(debug: bool = False) -> None:
    """初始化全局日志配置。

    在应用 lifespan 启动阶段调用一次。
    输出格式：JSON（生产）/ 彩色控制台（开发）。

    Args:
        debug: True 时输出 DEBUG 级别 + 彩色格式
    """
    level = logging.DEBUG if debug else logging.INFO

    # 根 logger
    root = logging.getLogger()
    root.setLevel(level)

    # 清除已有 handler
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if debug:
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        fmt = logging.Formatter(
            '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handler.setFormatter(fmt)
    root.addHandler(handler)

    # 降低第三方库日志噪音
    for lib in ("httpx", "openai", "pymilvus", "sqlalchemy.engine", "urllib3"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(f"logging_initialized level={'DEBUG' if debug else 'INFO'} format=json")


def get_logger(name: str) -> logging.Logger:
    """获取 logger 实例。

    Args:
        name: 通常传 __name__

    Returns:
        配置好的 Logger
    """
    return logging.getLogger(name)

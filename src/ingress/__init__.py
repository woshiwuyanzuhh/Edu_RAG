"""Ingestion Layer — 文档处理。独立部署单元，负责 parse → clean → chunk → embed → index。

对外唯一入口: IngestionService (IIngestionService 门面)
"""

from src.ingress.service import IngestionService

__all__ = ["IngestionService"]

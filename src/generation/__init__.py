"""Generation Layer — 生成。独立部署单元，负责基于上下文生成回答/考题。

对外唯一入口: GenerationService (IGenerationService 门面)
"""
from src.generation.service import GenerationService

__all__ = ["GenerationService"]

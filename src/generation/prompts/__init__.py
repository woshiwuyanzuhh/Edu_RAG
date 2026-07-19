"""Prompt 模板 — 集中管理所有 LLM 提示词。

变更 (v1.0 → v2.0):
    从代码中内嵌字符串提取为独立模块，方便版本管理和 A/B 测试。
"""

from src.generation.prompts.exam_generate import EXAM_GENERATE_PROMPT
from src.generation.prompts.exam_grade import GRADE_PROMPT
from src.generation.prompts.qa import QA_SYSTEM_PROMPT

__all__ = ["QA_SYSTEM_PROMPT", "EXAM_GENERATE_PROMPT", "GRADE_PROMPT"]

"""Guardrail: 输出安全过滤 + 引用溯源验证 — 输出侧安全检查。

检测：
    1. LLM 生成内容中的引用标注（[1] [2]）是否对应真实的检索结果
    2. 输出中是否包含不应出现的内容（简单敏感词过滤）
"""

import logging
import re

from src.interfaces.guardrail import GuardResult, IGuardrail

logger = logging.getLogger(__name__)

# 引用标注模式
CITATION_PATTERN = re.compile(r"\[(\d+)\]")


class OutputGuard(IGuardrail):
    """LLM 输出安全过滤器 + 引用验证器 — 实现 IGuardrail 接口。"""

    @property
    def is_blocking(self) -> bool:
        return False  # 非阻塞型：标记但不拒绝

    async def check(self, content: str, context: dict | None = None) -> GuardResult:
        """检查 LLM 输出的质量。"""
        if not content:
            return GuardResult(passed=True)

        flags = []

        # 引用溯源验证
        if context and context.get("chunks"):
            citations = CITATION_PATTERN.findall(content)
            max_chunks = len(context["chunks"])
            for cite_num in citations:
                if int(cite_num) > max_chunks:
                    flags.append(f"引用 [{cite_num}] 不存在（共 {max_chunks} 个来源）")

        # 幻觉关键词检测
        hallucination_markers = [
            "as an AI language model",
            "as a large language model",
            "according to my training data",
        ]
        for marker in hallucination_markers:
            if marker.lower() in content.lower():
                flags.append(f"输出包含通用 LLM 回复模式: {marker}")

        if flags:
            return GuardResult(
                passed=True,
                action="flag",
                reason="; ".join(flags),
                metadata={"flags": flags},
            )

        return GuardResult(passed=True)

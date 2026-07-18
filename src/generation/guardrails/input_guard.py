"""Guardrail: Prompt Injection 检测 — 输入侧安全检查。

检测已知的 prompt injection 模式：
    - "ignore previous instructions" / "忽略之前的指令"
    - "system prompt" 泄露尝试
    - "DAN" / jailbreak 关键词
"""
import re
import logging
from src.interfaces.guardrail import IGuardrail, GuardResult

logger = logging.getLogger(__name__)

# Prompt Injection 检测模式
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)",
    r"忽略(之前|前面|以上)的?(指令|提示|规则)",
    r"forget\s+(all\s+)?(previous|your)\s+(instructions?|training)",
    r"you\s+are\s+now\s+(DAN|STAN|jailbreak)",
    r"system\s*prompt\s*(is|:|：)",
    r"show\s+(me\s+)?your\s+(system\s+)?prompt",
    r"显示(你的)?(系统)?提示",
    r"pretend\s+(you\s+are|to\s+be)",
    r"假装(你是|你是)",
    r"act\s+as\s+if",
]


class InputGuard(IGuardrail):
    """Prompt Injection 检测器 — 实现 IGuardrail 接口。"""

    @property
    def is_blocking(self) -> bool:
        return True  # 阻塞型：检测到 injection 拒绝请求

    async def check(self, content: str, context: dict | None = None) -> GuardResult:
        """检测用户输入中的 prompt injection 模式。"""
        if not content:
            return GuardResult(passed=True)

        content_lower = content.lower()
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, content_lower):
                logger.warning(f"prompt_injection_detected pattern={pattern}")
                return GuardResult(
                    passed=False,
                    action="block",
                    reason="检测到不安全的输入模式，请求已被拒绝",
                    metadata={"pattern": pattern},
                )

        return GuardResult(passed=True)

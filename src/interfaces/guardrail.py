"""Guardrail 接口 — 横切 Generation 层的安全检查切面。

每个 Guardrail 检查输入/输出内容，返回 pass/block/flag 决策。

设计原则：
    - 安全类检查失败 → 拒绝（block）
    - 非安全类检查失败 → 标记但放行（flag）

风格统一：与同包其他接口一致，使用 ABC + @abstractmethod。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GuardResult:
    """Guardrail 检查结果。"""

    passed: bool = True
    action: str = "pass"  # "pass" | "block" | "flag"
    reason: str = ""
    metadata: dict = field(default_factory=dict)


class IGuardrail(ABC):
    """Guardrail 抽象基类 — 内容安全检查器。

    每个 Guardrail 实现一个特定的安全/质量检查。
    """

    @property
    @abstractmethod
    def is_blocking(self) -> bool:
        """是否为阻塞型检查（失败时拒绝请求）。"""
        ...

    @abstractmethod
    async def check(self, content: str, context: dict | None = None) -> GuardResult:
        """检查内容是否安全/合规。

        Args:
            content: 待检查的文本
            context: 额外的上下文信息（如 query、chunks）

        Returns:
            GuardResult: 检查结果
        """
        ...

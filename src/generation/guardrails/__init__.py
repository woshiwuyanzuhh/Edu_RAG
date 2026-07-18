"""Guardrails — Generation 层安全与质量切面。

输入侧：Prompt Injection 检测
输出侧：内容安全过滤 + 引用溯源验证 + 拒答决策

所有 Guard 实现 IGuardrail 接口，通过 GuardrailChain 链式调用。
"""
from src.generation.guardrails.chain import GuardrailChain

__all__ = ["GuardrailChain"]

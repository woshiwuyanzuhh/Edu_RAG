"""Guardrail 链式调用引擎 — 按序执行多个 Guard，按优先级决策。

降级策略：
    - 安全类 Guard 检查服务不可用 → 拒绝（block），保证安全
    - 非安全类 Guard 检查服务不可用 → 放行（pass），保证可用性
"""
import logging
from src.interfaces.guardrail import IGuardrail, GuardResult

logger = logging.getLogger(__name__)


class GuardrailChain:
    """Guardrail 链 — 按序执行多个 Guard。

    用法:
        chain = GuardrailChain([
            InputGuard(),
            OutputGuard(),
            RefuseGuard(),
        ])

        # 输入检查
        result = await chain.check_input(user_query)

        # 输出检查
        result = await chain.check_output(llm_answer, context={"query": query, "chunks": chunks})
    """

    def __init__(self, guards: list[IGuardrail] | None = None):
        self._guards: list[IGuardrail] = guards or []

    def add_guard(self, guard: IGuardrail) -> None:
        self._guards.append(guard)

    async def check_input(self, content: str, context: dict | None = None) -> GuardResult:
        """对用户输入执行所有 Guard 检查。

        Returns:
            聚合结果 — 任何阻塞型 Guard 失败则拒绝。
        """
        return await self._run_guards(content, context, stage="input")

    async def check_output(self, content: str, context: dict | None = None) -> GuardResult:
        """对 LLM 输出执行所有 Guard 检查。

        Returns:
            聚合结果 — 任何阻塞型 Guard 失败则拒绝。
        """
        return await self._run_guards(content, context, stage="output")

    async def _run_guards(self, content: str, context: dict | None, stage: str) -> GuardResult:
        """内部：按序执行 Guard，收集结果。"""
        flags: list[str] = []

        for guard in self._guards:
            guard_name = type(guard).__name__
            try:
                result = await guard.check(content, context)
                if result.action == "block":
                    logger.warning(f"guardrail_block stage={stage} guard={guard_name} reason={result.reason}")
                    return result  # 立刻拒绝
                if result.action == "flag":
                    flags.append(f"{guard_name}:{result.reason}")
                    logger.info(f"guardrail_flag stage={stage} guard={guard_name} reason={result.reason}")
            except Exception as e:
                if guard.is_blocking:
                    # 安全类 Guard 异常 → 拒绝（安全优先）
                    logger.error(f"guardrail_error_blocking stage={stage} guard={guard_name} error={e}")
                    return GuardResult(passed=False, action="block",
                                       reason=f"安全检查服务异常: {guard_name}")
                # 非阻塞 Guard 异常 → 忽略（可用性优先）
                logger.warning(f"guardrail_error_non_blocking stage={stage} guard={guard_name} error={e}")

        return GuardResult(passed=True, action="pass",
                           reason="; ".join(flags) if flags else "all checks passed")

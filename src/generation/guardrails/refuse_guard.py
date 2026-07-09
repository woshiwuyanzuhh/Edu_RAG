"""Guardrail: 拒答决策 — 上下文不足时拒绝编造。

原则：检索结果置信度过低时，系统应明确拒绝回答，而非编造信息。
"""
import logging
from src.shared.config import settings
from src.interfaces.guardrail import IGuardrail, GuardResult

logger = logging.getLogger(__name__)


class RefuseGuard:
    """拒答决策器 — 实现 IGuardrail 协议。"""

    def __init__(self, min_score: float | None = None):
        self._min_score = min_score if min_score is not None else settings.retrieval.min_score

    @property
    def is_blocking(self) -> bool:
        return True  # 阻塞型：质量不达标时拒绝生成

    async def check(self, content: str, context: dict | None = None) -> GuardResult:
        """检查检索结果是否足以支持回答。

        这里的 content 不是最终答案，而是上下文质量标志。
        context 中应包含检索的 chunks。
        """
        chunks = context.get("chunks", []) if context else []
        if not chunks:
            return GuardResult(
                passed=False,
                action="block",
                reason="当前知识库中暂无相关内容，建议上传相关资料后再提问。",
            )

        # 检查最高分是否达到最低阈值
        max_score = max((c.get("score", 0) for c in chunks), default=0)
        if max_score < self._min_score:
            return GuardResult(
                passed=False,
                action="block",
                reason="根据现有资料无法提供准确回答，建议补充相关知识库内容。",
                metadata={"max_score": max_score, "threshold": self._min_score},
            )

        return GuardResult(passed=True)

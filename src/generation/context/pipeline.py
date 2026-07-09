"""上下文增强管线 — 可插拔步骤链的执行引擎。

解决问题：原则 #3 — 新增功能 = 新增 Step 类 + 注册到管线，不改现有代码。
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.interfaces.context_processor import IContextProcessor

logger = logging.getLogger(__name__)


class ContextPipeline:
    """上下文增强管线 — 按序执行一组 IContextProcessor 步骤。

    用法:
        pipeline = ContextPipeline([
            RelevanceFilter(llm_client),
            SemanticCompressor(llm_client),
            LostInMiddleReorder(),
        ])

        enhanced_chunks = await pipeline.process(chunks, query)
        context = format_chunks(enhanced_chunks)  # 使用现有 build_context 逻辑
    """

    def __init__(self, steps: list["IContextProcessor"] | None = None):
        self._steps: list["IContextProcessor"] = steps or []

    @property
    def steps(self) -> list["IContextProcessor"]:
        return list(self._steps)

    def add_step(self, step: "IContextProcessor", position: int | None = None) -> None:
        """添加步骤。

        Args:
            step: IContextProcessor 实例
            position: 插入位置（None 表示追加到末尾）
        """
        if position is None:
            self._steps.append(step)
        else:
            self._steps.insert(max(0, min(position, len(self._steps))), step)

    def remove_step(self, step_class: type) -> None:
        """按类型移除步骤。"""
        self._steps = [s for s in self._steps if not isinstance(s, step_class)]

    async def process(self, chunks: list[dict], query: str) -> list[dict]:
        """按序执行所有步骤。

        Args:
            chunks: [{"text": str, "score": float, "metadata": dict}, ...]
            query: 用户原始查询

        Returns:
            处理后的 chunks 列表
        """
        if not chunks:
            return []

        result = chunks
        for step in self._steps:
            step_name = type(step).__name__
            before = len(result)
            try:
                result = await step.process(result, query)
                after = len(result)
                if before != after:
                    logger.debug(f"context_pipeline_step {step_name} {before}→{after} chunks")
            except Exception as e:
                logger.warning(f"context_pipeline_step_failed step={step_name} error={e}")
                # 步骤失败 → 跳过该步骤，继续执行后续步骤
                continue

        return result

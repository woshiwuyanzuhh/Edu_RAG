"""上下文增强管线 — Generation 层 Pre-Generation 阶段。

可插拔步骤链：RelevanceFilter → SemanticCompressor → LostInMiddleReorder

每个 Step 实现 IContextProcessor 接口。
通过 ContextPipeline 组装和配置。
"""
from src.generation.context.pipeline import ContextPipeline

__all__ = ["ContextPipeline"]

"""Query 预处理器 — 向后兼容 re-export。

⚠️ Deprecated: hyde_expand 已下沉到 src.generation.hyde。
    Generation 层持有 ILLMClient，HyDE 属于 Generation 职责。
    此前放在 Orchestration 层导致 GenerationService 反向依赖顶层（违规）。

    新代码请直接 from src.generation.hyde import hyde_expand。
    本模块保留仅为向后兼容，依赖方向：Orchestration(上) → Generation(下) 合法。
"""
from src.generation.hyde import hyde_expand, HYDE_PROMPT

__all__ = ["hyde_expand", "HYDE_PROMPT"]

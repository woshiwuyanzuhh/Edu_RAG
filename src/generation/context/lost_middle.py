"""上下文管线 Step 3: LostInMiddleReorder — "Lost in the Middle" 注意力重排。

从 retrieval/filters.py 迁移至此，作为管线的一个可插拔步骤。

原理 (Liu et al., 2023)：LLM 对长文本首部和尾部的注意力显著高于中间。
策略：最高分→头部，次高分→尾部，其余按分数排列在中间。
"""
import logging

logger = logging.getLogger(__name__)


class LostInMiddleReorder:
    """"Lost in the Middle" 重排器 — 实现 IContextProcessor 协议。"""

    async def process(self, chunks: list[dict], query: str) -> list[dict]:
        """对 chunks 重新排序，不增删内容。"""
        if len(chunks) <= 3:
            return list(chunks)

        # chunks 已是按 score 降序
        best = chunks[0]
        second_best = chunks[1]
        middle = sorted(chunks[2:], key=lambda x: x.get("score", 0), reverse=True)

        result = [best] + middle + [second_best]
        logger.debug(f"lost_middle_reorder {len(chunks)} chunks")
        return result

"""上下文管线 Step 2: SemanticCompressor — LLM 逐块提取关键句。

解决问题：原则 #7 — 上下文质量优先于上下文长度。减少噪声 token，提高 LLM 注意力。

P2-7 优化: 使用 asyncio.gather 并发压缩多块，Semaphore 限流避免 LLM 限速。
"""
import asyncio
import logging
from src.interfaces.llm import ILLMClient, Message
from src.interfaces.context_processor import IContextProcessor
from src.generation.prompts.compress import COMPRESS_PROMPT

logger = logging.getLogger(__name__)


class SemanticCompressor(IContextProcessor):
    """LLM 语义压缩器 — 实现 IContextProcessor 接口。"""

    def __init__(self, llm_client: ILLMClient, min_chunk_len: int = 200, max_concurrency: int = 5):
        self._llm = llm_client
        self._min_chunk_len = min_chunk_len  # 短于这个长度不压缩
        self._max_concurrency = max_concurrency  # P2-7: 并发限流，避免 LLM 限速

    async def process(self, chunks: list[dict], query: str) -> list[dict]:
        """P2-7: 并发压缩 — 只对超过 min_chunk_len 的块调用 LLM 压缩，Semaphore 限流。"""
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def compress_one(c: dict) -> dict:
            text = c.get("text", "")
            # 短文本不压缩，直接返回
            if len(text) <= self._min_chunk_len:
                return c

            async with semaphore:
                try:
                    prompt = COMPRESS_PROMPT.format(question=query, chunk_text=text)
                    compressed = await self._llm.chat(
                        messages=[Message(role="user", content=prompt)],
                        temperature=0.1,
                        max_tokens=max(256, len(text) // 2),
                    )
                    compressed = compressed.strip()
                    if compressed and compressed != "不相关" and len(compressed) > 20:
                        return {**c, "text": compressed, "metadata": {**c.get("metadata", {}), "compressed": True}}
                    else:
                        return c  # 不相关或太短，保留原文
                except Exception as e:
                    logger.warning(f"compressor_failed error={e}")
                    return c  # 失败时保留原文

        # P2-7: 并发执行所有块的压缩
        result = await asyncio.gather(*[compress_one(c) for c in chunks])
        result_list = list(result)
        logger.debug(f"semantic_compressor {len(chunks)}→{len(result_list)} concurrency={self._max_concurrency}")
        return result_list

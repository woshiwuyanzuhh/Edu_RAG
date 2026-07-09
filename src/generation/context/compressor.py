"""上下文管线 Step 2: SemanticCompressor — LLM 逐块提取关键句。

解决问题：原则 #7 — 上下文质量优先于上下文长度。减少噪声 token，提高 LLM 注意力。
"""
import logging
from src.interfaces.llm import ILLMClient, Message
from src.generation.prompts.compress import COMPRESS_PROMPT

logger = logging.getLogger(__name__)


class SemanticCompressor:
    """LLM 语义压缩器 — 实现 IContextProcessor 协议。"""

    def __init__(self, llm_client: ILLMClient, min_chunk_len: int = 200):
        self._llm = llm_client
        self._min_chunk_len = min_chunk_len  # 短于这个长度不压缩

    async def process(self, chunks: list[dict], query: str) -> list[dict]:
        """逐块压缩 — 只对超过 min_chunk_len 的块调用 LLM 压缩。"""
        result = []
        for c in chunks:
            text = c.get("text", "")
            if len(text) <= self._min_chunk_len:
                result.append(c)  # 短文本不压缩
                continue

            try:
                prompt = COMPRESS_PROMPT.format(question=query, chunk_text=text)
                compressed = await self._llm.chat(
                    messages=[Message(role="user", content=prompt)],
                    temperature=0.1,
                    max_tokens=max(256, len(text) // 2),
                )
                compressed = compressed.strip()
                if compressed and compressed != "不相关" and len(compressed) > 20:
                    result.append({**c, "text": compressed, "metadata": {**c.get("metadata", {}), "compressed": True}})
                else:
                    result.append(c)  # 不相关或太短，保留原文
            except Exception as e:
                logger.warning(f"compressor_failed error={e}")
                result.append(c)  # 失败时保留原文

        logger.debug(f"semantic_compressor {len(chunks)}→{len(result)}")
        return result

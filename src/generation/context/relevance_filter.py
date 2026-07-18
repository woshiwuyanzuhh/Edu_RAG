"""上下文管线 Step 1: RelevanceFilter — LLM 判断每个 chunk 是否与 query 相关。

解决问题：检索后上下文质量二次验证。过滤不相关 chunk，减少噪声。
"""
import json
import logging
from src.interfaces.llm import ILLMClient, Message
from src.interfaces.context_processor import IContextProcessor

logger = logging.getLogger(__name__)

FILTER_PROMPT = """你是一个信息检索质量审核员。判断以下文本片段是否与用户问题相关。

## 用户问题
{question}

## 需要判断的片段
{chunks_text}

## 输出要求
仅输出 JSON 数组，每个元素包含 id（片段编号）和 relevant（true/false）：
```json
[
  {{"id": 1, "relevant": true}},
  {{"id": 2, "relevant": false}}
]
```

判断标准：
- 直接回答问题的 → true
- 包含问题相关的核心概念 → true
- 完全不相关或只有表面文字匹配 → false"""


class RelevanceFilter(IContextProcessor):
    """LLM 相关性过滤器 — 实现 IContextProcessor 接口。"""

    def __init__(self, llm_client: ILLMClient, min_chunks: int = 3):
        self._llm = llm_client
        self._min_chunks = min_chunks  # 最少保留数量，避免过度过滤

    async def process(self, chunks: list[dict], query: str) -> list[dict]:
        if len(chunks) <= self._min_chunks:
            return chunks  # 太少，不值得过滤

        # 构造 prompt
        parts = [f"[{i + 1}] {c['text'][:300]}" for i, c in enumerate(chunks)]
        prompt = FILTER_PROMPT.format(question=query, chunks_text="\n\n".join(parts))

        try:
            response = await self._llm.chat(
                messages=[Message(role="user", content=prompt)],
                temperature=0.1,
                max_tokens=512,
            )
            # 解析
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1].rsplit("```", 1)[0]
            rulings = json.loads(response)

            relevant_indices = {item["id"] - 1 for item in rulings if item.get("relevant")}
            filtered = [c for i, c in enumerate(chunks) if i in relevant_indices]

            # 兜底：至少保留 min_chunks 个
            if len(filtered) < self._min_chunks:
                filtered = chunks[:self._min_chunks]

            logger.debug(f"relevance_filter {len(chunks)}→{len(filtered)}")
            return filtered

        except Exception as e:
            logger.warning(f"relevance_filter_failed error={e} — passing through")
            return chunks  # 失败时透传，不影响管线

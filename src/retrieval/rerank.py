"""
精排重排模块 — 两阶段检索的第二阶段。

解决问题 #10: 截断策略改进 — 取首尾各 150 字符，不丢失尾部信息。
解决问题 #11: 分数融合 — final = α × LLM_score + (1-α) × vector_score。
"""

import logging

from src.interfaces.llm import ILLMClient, Message
from src.interfaces.vector_store import SearchResult
from src.shared.config import settings
from src.shared.json_utils import try_parse_llm_json

logger = logging.getLogger(__name__)

RERANK_PROMPT = """你是一个信息检索专家。下面有多个从文档中检索到的候选片段。
请根据用户问题，选出最相关的 {top_k} 个片段，按相关度从高到低排列。

## 用户问题
{question}

## 候选片段
{candidates_text}

## 输出要求
仅输出 JSON 数组，不要其他文字。每个元素包含 id（片段编号）和 score（1-10 的相关度评分）：
```json
[
  {{"id": 3, "score": 10}},
  {{"id": 7, "score": 8}},
  ...
]
```

选择标准：
1. 直接回答问题的片段优先
2. 包含核心概念定义的优先
3. 提供相关背景或上下文的次之
4. 表面文字匹配但语义不相关的排除"""


def _truncate_head_tail(text: str, max_chars: int = 300) -> str:
    """首尾截断 — 取前 + 后各一半，不丢失尾部关键信息。解决问题 #10。

    Args:
        text: 原始文本
        max_chars: 目标字符数

    Returns:
        截断后的文本
    """
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n...\n" + text[-half:]


async def llm_rerank(
    query: str,
    candidates: list[SearchResult],
    llm_client: ILLMClient,
    top_k: int = 5,
    fusion_alpha: float | None = None,
) -> list[SearchResult]:
    """LLM 精排重排 + 分数融合。

    Args:
        query: 用户查询
        candidates: 粗排候选（需 > top_k 才执行重排）
        llm_client: LLM 客户端
        top_k: 返回数量
        fusion_alpha: 向量分数融合权重 (0=纯向量, 1=纯LLM)

    Returns:
        精排后的 top_k 结果
    """
    if fusion_alpha is None:
        fusion_alpha = settings.retrieval.fusion_alpha

    if len(candidates) <= top_k:
        return candidates

    # 构造候选文本
    parts = []
    for i, c in enumerate(candidates):
        snippet = _truncate_head_tail(c.text, max_chars=300)
        parts.append(f"[{i + 1}] {snippet}")

    prompt = RERANK_PROMPT.format(
        top_k=top_k,
        question=query,
        candidates_text="\n\n".join(parts),
    )

    try:
        response = await llm_client.chat(
            messages=[Message(role="user", content=prompt)],
            temperature=0.1,
            max_tokens=1024,
        )
    except Exception as e:
        logger.warning(f"rerank_llm_failed error={e}")
        return candidates[:top_k]

    # P2-2: 使用 shared.json_utils 解析（容错模式，失败时降级返回原始排序）
    rankings = try_parse_llm_json(response, default=None)
    if rankings is None:
        return candidates[:top_k]

    # 分数融合（解决问题 #11）
    id_to_candidate: dict[int, SearchResult] = {i + 1: c for i, c in enumerate(candidates)}
    fused: list[SearchResult] = []
    for item in rankings:
        cid = item.get("id", 0)
        if cid in id_to_candidate:
            c = id_to_candidate[cid]
            try:
                raw = item.get("score", 0)
                llm_score = max(0.0, min(1.0, float(raw) / 10.0))  # 归一化 + clamp + 防非数字
            except (TypeError, ValueError):
                llm_score = 0.0
            original_vec_score = c.score
            fused_score = round(fusion_alpha * llm_score + (1 - fusion_alpha) * original_vec_score, 4)
            fused.append(
                SearchResult(
                    id=c.id,
                    text=c.text,
                    score=fused_score,
                    metadata={
                        **c.metadata,
                        "llm_score": llm_score,
                        "vector_score": original_vec_score,
                    },
                )
            )

    logger.debug(f"rerank_complete before={len(candidates)} after={len(fused)}")
    return fused[:top_k]

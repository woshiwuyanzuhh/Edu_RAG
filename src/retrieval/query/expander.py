"""
LLM 查询扩展器 — 将用户问题改写为多个不同角度的搜索查询。

解决问题 #1 (Redis 缓存): 扩展结果带缓存，相同问题不重复调 LLM。
解决问题 #15: 被 recall 模块以 batch embedding 方式调用。
"""
import re
import hashlib
import logging
from src.interfaces.query_expander import IQueryExpander
from src.interfaces.llm import ILLMClient, Message
from src.shared.cache import cache_strategy

logger = logging.getLogger(__name__)

QUERY_EXPAND_PROMPT = """将用户问题改写成 4 个不同角度的搜索查询，覆盖问题可能涉及的不同方面和不同的表达方式。

规则：
- 每行一个查询，不要编号
- 使用简洁的关键词组合
- 覆盖不同的角度和表述方式
- 用户问题是中文就用中文输出，是英文就用英文输出

用户问题：{question}

查询："""


class LLMQueryExpander(IQueryExpander):
    """基于 LLM 的查询扩展器。"""

    def __init__(self, llm_client: ILLMClient):
        self._llm = llm_client

    async def expand(self, question: str, n: int = 4) -> list[str]:
        # L2 缓存检查
        cache_key = f"edu_rag:query_expand:{hashlib.sha256(question.encode()).hexdigest()[:16]}"
        cached = await cache_strategy.get(cache_key)
        if cached:
            logger.debug(f"query_expand_cache_hit question={question[:50]}")
            return cached

        try:
            prompt = QUERY_EXPAND_PROMPT.format(question=question)
            response = await self._llm.chat(
                messages=[Message(role="user", content=prompt)],
                temperature=0.3,
                max_tokens=200,
            )
            queries = [q.strip() for q in response.strip().split("\n") if q.strip()]
            queries = [re.sub(r'^\d+[.\)\-]?\s*', '', q) for q in queries]

            if question not in queries:
                queries.insert(0, question)
            result = queries[:n]

            # 缓存结果 (TTL=600s)
            await cache_strategy.set(cache_key, result, ttl=600)
            logger.debug(f"query_expand_done count={len(result)}")
            return result

        except Exception:
            logger.warning(f"query_expand_failed question={question[:50]}", exc_info=True)
            return [question]

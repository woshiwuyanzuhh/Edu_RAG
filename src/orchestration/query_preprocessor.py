"""Query 预处理器 — 在调用 Retrieval 之前对用户查询进行增强。

Phase 4 P3-2: HyDE (Hypothetical Document Embeddings)
    - 让 LLM 生成一个假设性答案
    - 用假设答案做 embedding 检索
    - 原理：答案与文档处于同一语义空间，检索效果优于直接查问题

架构决策：HyDE 放在 Orchestration 层而非 Retrieval 层，因为它需要 LLM。
"需要 LLM 的操作不属于 Retrieval" — 《架构演进建议》原则 1。
"""
import logging
from src.interfaces.llm import ILLMClient, Message

logger = logging.getLogger(__name__)

HYDE_PROMPT = """你是一个知识问答助手。请根据以下问题，写一段假设性的回答。

注意：
- 不要使用外部知识，仅基于常识和推理
- 回答长度控制在 100-200 字
- 用中文回答

问题：{question}

假设性回答："""


async def hyde_expand(question: str, llm_client: ILLMClient) -> str:
    """生成假设性答案用于检索。

    Args:
        question: 用户原始问题
        llm_client: LLM 客户端

    Returns:
        假设性答案文本（用于替代原始 query 做 embedding）
    """
    try:
        prompt = HYDE_PROMPT.format(question=question)
        hypothetical_answer = await llm_client.chat(
            messages=[Message(role="user", content=prompt)],
            temperature=0.7,
            max_tokens=300,
        )
        hypothetical_answer = hypothetical_answer.strip()
        if hypothetical_answer:
            logger.info(f"hyde_generated len={len(hypothetical_answer)}")
            return hypothetical_answer
    except Exception as e:
        logger.warning(f"hyde_failed error={e} — falling back to original query")

    return question  # 降级：返回原始问题

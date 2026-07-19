"""HyDE (Hypothetical Document Embeddings) 查询增强。

Phase 4 P3-2: 让 LLM 生成一个假设性答案，用假设答案做 embedding 检索。
原理：答案与文档处于同一语义空间，检索效果优于直接查问题。

架构说明：
    HyDE 需要 LLM，属于 Generation 层职责（Generation 持有 ILLMClient）。
    此前 hyde_expand 放在 orchestration/query_preprocessor.py，导致
    GenerationService 反向依赖 Orchestration 层（底层依赖顶层，违规）。
    现下沉到 Generation 层，修复分层违规。Orchestration 层如需调用，
    应通过 IGenerationService 接口，而非直接 import 本模块。
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
        假设性答案文本（用于替代原始 query 做 embedding）；失败时降级返回原问题。
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

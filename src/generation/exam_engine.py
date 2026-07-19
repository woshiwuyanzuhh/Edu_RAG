"""
题库引擎 — 智能出题 + 自动批改。

解决问题 #19: 出题和批改支持流式输出。
解决问题 #24: 批改增加四维度评分（概念/分析/记忆/应用）。
架构原则 #4: 所有检索操作通过 IRetrievalService 接口调用。

变更 (Opt-13): 接入 ContextPipeline — 考试上下文也走管线增强。
P2-2: 抽取 _prepare_exam_context 消除 generate_exam / generate_exam_stream 重复；JSON 解析改用 shared.json_utils。
"""

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from src.generation.prompts.exam_generate import EXAM_GENERATE_PROMPT
from src.generation.prompts.exam_grade import GRADE_PROMPT
from src.interfaces.llm import ILLMClient, Message
from src.interfaces.retrieval_service import IRetrievalService
from src.shared.json_utils import parse_llm_json

if TYPE_CHECKING:
    from src.generation.context.pipeline import ContextPipeline

logger = logging.getLogger(__name__)

TYPE_NAMES = {
    "choice": "选择题",
    "essay": "简答题",
    "tf": "判断题",
    "mixed": "选择题、简答题和判断题混合",
}


async def _prepare_exam_context(
    knowledge_base_id: int,
    retrieval_svc: IRetrievalService,
    question_type: str,
    question_count: int,
    difficulty: str,
    pipeline: "ContextPipeline | None",
) -> str:
    """P2-2: 抽取出题共通的检索 + 管线增强 + prompt 构造。

    被 generate_exam 和 generate_exam_stream 共用，消除重复的 pipeline 增强 + prompt 构造逻辑。
    """
    # 1. 多角度检索
    context = await retrieval_svc.build_context_for_exam(knowledge_base_id)

    # Opt-13: 管线增强（如果提供）
    if pipeline:
        hits = await retrieval_svc.retrieve(
            query=f"{question_type} {difficulty} 考试题目",
            knowledge_base_id=knowledge_base_id,
            top_k=10,
            use_rerank=False,
        )
        if hits:
            chunks = [{"text": h.text, "score": h.score, "metadata": h.metadata or {}} for h in hits]
            enhanced = await pipeline.process(chunks, f"{difficulty}难度{question_type}")
            from src.generation.qa_engine import _chunks_to_context

            context = _chunks_to_context(enhanced)

    # 2. 构造 prompt
    type_name = TYPE_NAMES.get(question_type, "选择题")
    prompt = EXAM_GENERATE_PROMPT.format(
        context=context,
        question_type=type_name,
        question_count=question_count,
        difficulty=difficulty,
    )
    return prompt


async def generate_exam(
    knowledge_base_id: int,
    llm_client: ILLMClient,
    retrieval_svc: IRetrievalService,
    question_type: str = "mixed",
    question_count: int = 5,
    difficulty: str = "medium",
    pipeline: "ContextPipeline | None" = None,
) -> list[dict]:
    """生成考试题目。"""
    # P2-2: 使用抽取的 _prepare_exam_context
    prompt = await _prepare_exam_context(
        knowledge_base_id,
        retrieval_svc,
        question_type,
        question_count,
        difficulty,
        pipeline,
    )

    # 3. 调用 LLM
    response = await llm_client.chat(
        messages=[
            Message(role="system", content="你是专业的教育考试出题专家，请严格按照 JSON 格式输出题目。"),
            Message(role="user", content=prompt),
        ],
        temperature=0.8,
        max_tokens=4096,
    )

    # 4. 解析 JSON（P2-2: 改用 shared.json_utils）
    return parse_llm_json(response, "题目")


async def generate_exam_stream(
    knowledge_base_id: int,
    llm_client: ILLMClient,
    retrieval_svc: IRetrievalService,
    question_type: str = "mixed",
    question_count: int = 5,
    difficulty: str = "medium",
    pipeline: "ContextPipeline | None" = None,
) -> AsyncGenerator[str, None]:
    """流式出题。"""
    # P2-2: 使用抽取的 _prepare_exam_context
    prompt = await _prepare_exam_context(
        knowledge_base_id,
        retrieval_svc,
        question_type,
        question_count,
        difficulty,
        pipeline,
    )

    async for token in llm_client.chat_stream(
        messages=[
            Message(role="system", content="你是专业的教育考试出题专家，请严格按照 JSON 格式输出题目。"),
            Message(role="user", content=prompt),
        ],
        temperature=0.8,
        max_tokens=4096,
    ):
        yield token


async def grade_exam(
    questions: list[dict],
    student_answers: list[dict],
    knowledge_base_id: int,
    llm_client: ILLMClient,
    retrieval_svc: IRetrievalService,
) -> dict:
    """批改考试答案（含维度评分）。

    Returns:
        {total_score, max_score, details, dimensions, summary}
    """
    question_count = max(len(questions), 1)
    per_question_max = 100.0 / question_count
    max_score = 100.0

    # 1. 检索 + 构建上下文
    result = await retrieval_svc.retrieve_with_context(
        query=" ".join([q.get("stem", "") for q in questions]),
        knowledge_base_id=knowledge_base_id,
        top_k=8,
        use_rerank=False,
    )
    context = result["context"]

    # 2. 构造答案文本
    reference_parts = []
    for q in questions:
        ref = f"第{q['number']}题 ({q.get('type', 'essay')})\n题干: {q['stem']}"
        if q.get("options"):
            ref += "\n选项: " + ", ".join(q["options"])
        ref += f"\n参考答案: {q.get('answer', '')}"
        reference_parts.append(ref)

    student_parts = [f"第{a.get('number', '?')}题答案: {a.get('answer', '')}" for a in student_answers]

    prompt = GRADE_PROMPT.format(
        context=context,
        reference="\n\n".join(reference_parts),
        student_answer="\n\n".join(student_parts),
        per_question_max=per_question_max,
    )

    # 3. LLM 批改
    response = await llm_client.chat(
        messages=[
            Message(role="system", content="你是严格公正的阅卷老师，请严格按 JSON 格式输出评分结果。"),
            Message(role="user", content=prompt),
        ],
        temperature=0.3,
        max_tokens=2048,
    )

    # 4. 解析（P2-2: 改用 shared.json_utils）
    result = parse_llm_json(response, "批改结果")
    if isinstance(result, list):
        details = result
        dimensions = None
    else:
        details = result.get("details") or []
        dimensions = result.get("dimensions")

    total_score = sum(d.get("score", 0) for d in details)

    # 5. 生成总结
    summary = _score_summary(total_score)

    return {
        "total_score": total_score,
        "max_score": max_score,
        "details": details,
        "dimensions": dimensions,
        "summary": summary,
    }


# ── 工具函数 ──


def _score_summary(total_score: float) -> str:
    """分数段位总结。"""
    if total_score >= 90:
        return "优秀！你对知识点的掌握非常扎实，继续保持！"
    elif total_score >= 75:
        return "良好，大部分知识点都已掌握，部分内容可以进一步巩固。"
    elif total_score >= 60:
        return "及格，还有提升空间，建议复习相关知识点后重新测试。"
    else:
        return "需要加强学习，建议系统回顾知识库内容后再做一次测试。"

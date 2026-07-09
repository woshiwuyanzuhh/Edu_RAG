"""Generation 服务门面 — Generation 层唯一对外入口。

封装 qa_engine + exam_engine，依赖注入 ILLMClient + IRetrievalService。

变更 (Phase 2 P1-5): 集成 ContextPipeline
变更 (Opt-6): Feature Flags 动态组装管线步骤
变更 (Opt-7): 集成 GuardrailChain
"""
import logging
from typing import AsyncGenerator

from src.shared.config import settings
from src.interfaces.generation_service import IGenerationService
from src.interfaces.llm import ILLMClient
from src.interfaces.retrieval_service import IRetrievalService
from src.generation.qa_engine import qa_non_stream, qa_stream
from src.generation.exam_engine import generate_exam, grade_exam, generate_exam_stream
from src.generation.context.pipeline import ContextPipeline
from src.generation.context.lost_middle import LostInMiddleReorder
from src.generation.guardrails.chain import GuardrailChain
from src.generation.guardrails.input_guard import InputGuard
from src.generation.guardrails.output_guard import OutputGuard
from src.generation.guardrails.refuse_guard import RefuseGuard

logger = logging.getLogger(__name__)


class GenerationService(IGenerationService):
    """Generation 服务实现 — 依赖注入 LLM + Retrieval + ContextPipeline + Guardrails。"""

    def __init__(
        self,
        llm_client: ILLMClient,
        retrieval_svc: IRetrievalService,
        pipeline: ContextPipeline | None = None,
        guardrails: GuardrailChain | None = None,
    ):
        self._llm = llm_client
        self._retrieval = retrieval_svc
        self._pipeline = pipeline or self._build_pipeline()
        self._guardrails = guardrails or self._build_guardrails()

    def _build_pipeline(self) -> ContextPipeline:
        """根据 Feature Flags 动态组装上下文增强管线。"""
        steps = []

        if settings.generation.enable_relevance_filter:
            from src.generation.context.relevance_filter import RelevanceFilter
            steps.append(RelevanceFilter(self._llm))

        if settings.generation.enable_compression:
            from src.generation.context.compressor import SemanticCompressor
            steps.append(SemanticCompressor(self._llm))

        if settings.generation.enable_lost_middle:
            steps.append(LostInMiddleReorder())

        return ContextPipeline(steps)

    def _build_guardrails(self) -> GuardrailChain:
        """根据配置组装 Guardrail 链。"""
        guards = [InputGuard(), RefuseGuard(), OutputGuard()]
        return GuardrailChain(guards)

    async def _get_query(self, question: str) -> str:
        """可选 HyDE 扩展 — 根据 Feature Flag 决定。"""
        if settings.generation.enable_hyde:
            from src.orchestration.query_preprocessor import hyde_expand
            return await hyde_expand(question, self._llm)
        return question

    async def qa(
        self,
        question: str,
        knowledge_base_id: int | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
        history: list[dict] | None = None,
    ) -> dict:
        query = await self._get_query(question)
        return await qa_non_stream(
            question=query,
            llm_client=self._llm,
            retrieval_svc=self._retrieval,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            use_rerank=use_rerank,
            history=history,
            pipeline=self._pipeline,
            guardrails=self._guardrails,
        )

    async def qa_stream(
        self,
        question: str,
        knowledge_base_id: int | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        query = await self._get_query(question)
        async for chunk in qa_stream(
            question=query,
            llm_client=self._llm,
            retrieval_svc=self._retrieval,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            use_rerank=use_rerank,
            history=history,
            pipeline=self._pipeline,
            guardrails=self._guardrails,
        ):
            yield chunk

    async def generate_exam(
        self,
        knowledge_base_id: int,
        question_type: str = "mixed",
        question_count: int = 5,
        difficulty: str = "medium",
    ) -> list[dict]:
        return await generate_exam(
            knowledge_base_id=knowledge_base_id,
            llm_client=self._llm,
            retrieval_svc=self._retrieval,
            question_type=question_type,
            question_count=question_count,
            difficulty=difficulty,
            pipeline=self._pipeline,
        )

    async def generate_exam_stream(
        self,
        knowledge_base_id: int,
        question_type: str = "mixed",
        question_count: int = 5,
        difficulty: str = "medium",
    ) -> AsyncGenerator[str, None]:
        async for token in generate_exam_stream(
            knowledge_base_id=knowledge_base_id,
            llm_client=self._llm,
            retrieval_svc=self._retrieval,
            question_type=question_type,
            question_count=question_count,
            difficulty=difficulty,
            pipeline=self._pipeline,
        ):
            yield token

    async def grade_exam(
        self,
        questions: list[dict],
        student_answers: list[dict],
        knowledge_base_id: int,
    ) -> dict:
        return await grade_exam(
            questions=questions,
            student_answers=student_answers,
            knowledge_base_id=knowledge_base_id,
            llm_client=self._llm,
            retrieval_svc=self._retrieval,
        )

"""Generation 服务接口 — Generation 层唯一对外门面。

Orchestration 层通过此接口调用生成能力，不直接依赖 qa_engine / exam_engine 内部模块。

解决问题：原则 #2 — 每层必须且只能暴露一个 Facade 接口。
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class IGenerationService(ABC):
    """Generation 服务抽象 — 封装 QA 问答 + 考试出题/批改。"""

    @abstractmethod
    async def qa(
        self,
        question: str,
        knowledge_base_id: int | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
        history: list[dict] | None = None,
    ) -> dict:
        """非流式 RAG 问答。

        Returns:
            {"question": str, "answer": str, "sources": list[dict]}
        """
        ...

    @abstractmethod
    async def qa_stream(
        self,
        question: str,
        knowledge_base_id: int | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式 RAG 问答 — 返回 SSE 事件流。"""
        ...

    @abstractmethod
    async def generate_exam(
        self,
        knowledge_base_id: int,
        question_type: str = "mixed",
        question_count: int = 5,
        difficulty: str = "medium",
    ) -> list[dict]:
        """生成考试题目。

        Returns:
            题目列表 [{"number": int, "type": str, "stem": str, "options": list|None, "answer": str}]
        """
        ...

    @abstractmethod
    async def generate_exam_stream(
        self,
        knowledge_base_id: int,
        question_type: str = "mixed",
        question_count: int = 5,
        difficulty: str = "medium",
    ) -> AsyncGenerator[str, None]:
        """流式出题 — SSE。"""
        ...

    @abstractmethod
    async def grade_exam(
        self,
        questions: list[dict],
        student_answers: list[dict],
        knowledge_base_id: int,
    ) -> dict:
        """批改考试答案。

        Returns:
            {"total_score": float, "max_score": float, "details": list, "dimensions": dict|None, "summary": str}
        """
        ...

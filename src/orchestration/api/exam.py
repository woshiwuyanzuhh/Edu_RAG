"""考试 API — 出题 + 批改 + 记录。

变更 (Phase 1 P0-5): 通过 IGenerationService 门面调用，不再直接
import generation 内部模块。
"""
import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.mysql import get_db
from src.shared.models.orm import KnowledgeBase, ExamRecord
from src.shared.models.schemas import (
    APIResponse, ExamGenerateRequest, ExamGradeRequest, QuestionItem,
)
from src.shared.exceptions import NotFoundError, ValidationError
from src.orchestration.services import get_generation_service
from src.orchestration.pagination import paginate, get_offset_limit, paginated_select
from src.orchestration.middleware.metrics import EXAM_REQUESTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/exam", tags=["题库"])


@router.post("/generate", response_model=APIResponse)
async def generate_questions(req: ExamGenerateRequest, db: AsyncSession = Depends(get_db)):
    kb = await db.get(KnowledgeBase, req.knowledge_base_id)
    if not kb:
        raise NotFoundError("知识库不存在")

    gen_svc = get_generation_service()
    try:
        questions = await gen_svc.generate_exam(
            knowledge_base_id=req.knowledge_base_id,
            question_type=req.question_type,
            question_count=req.question_count,
            difficulty=req.difficulty,
        )
        EXAM_REQUESTS.labels(question_type=req.question_type, action="generate").inc()
    except Exception as e:
        EXAM_REQUESTS.labels(question_type=req.question_type, action="generate_error").inc()
        raise ValidationError(f"出题失败: {str(e)}")

    record = ExamRecord(
        knowledge_base_id=req.knowledge_base_id,
        question_type=req.question_type,
        question_count=len(questions),
        difficulty=req.difficulty,
        questions=questions,
        status="draft",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    question_items = [
        QuestionItem(number=q.get("number", 0), type=q.get("type", "essay"),
                     stem=q.get("stem", ""), options=q.get("options"), answer=q.get("answer", ""))
        for q in questions
    ]

    return APIResponse(message=f"成功生成 {len(questions)} 道题目", data={
        "exam_id": record.id, "knowledge_base_id": req.knowledge_base_id,
        "question_type": req.question_type, "question_count": len(questions),
        "questions": [item.model_dump() for item in question_items],
    })


@router.post("/generate/stream")
async def generate_questions_stream(req: ExamGenerateRequest, db: AsyncSession = Depends(get_db)):
    """流式出题。"""
    kb = await db.get(KnowledgeBase, req.knowledge_base_id)
    if not kb:
        raise NotFoundError("知识库不存在")

    gen_svc = get_generation_service()

    async def generate():
        async for token in gen_svc.generate_exam_stream(
            knowledge_base_id=req.knowledge_base_id,
            question_type=req.question_type,
            question_count=req.question_count,
            difficulty=req.difficulty,
        ):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/grade", response_model=APIResponse)
async def grade_answers(req: ExamGradeRequest, db: AsyncSession = Depends(get_db)):
    record = await db.get(ExamRecord, req.exam_id)
    if not record:
        raise NotFoundError("考试记录不存在")

    questions = record.questions or []
    if not questions:
        raise ValidationError("考试记录中没有题目")

    # 先保存答案
    record.answers = req.answers
    record.status = "answered"
    await db.commit()

    gen_svc = get_generation_service()
    try:
        result = await gen_svc.grade_exam(
            questions=questions,
            student_answers=req.answers,
            knowledge_base_id=record.knowledge_base_id,
        )
        EXAM_REQUESTS.labels(question_type=record.question_type, action="grade").inc()
    except Exception as e:
        EXAM_REQUESTS.labels(question_type=record.question_type, action="grade_error").inc()
        raise ValidationError(f"批改失败: {str(e)}")

    record.scores = result["details"]
    record.dimensions = result.get("dimensions")
    record.total_score = result["total_score"]
    record.max_score = result["max_score"]
    record.status = "graded"
    await db.commit()

    return APIResponse(message="批改完成", data={
        "exam_id": record.id, "total_score": result["total_score"], "max_score": result["max_score"],
        "details": result["details"], "dimensions": result.get("dimensions"), "summary": result["summary"],
    })


@router.get("/records", response_model=APIResponse)
async def list_exam_records(
    knowledge_base_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # P2-2: 使用 paginated_select 消除重复的分页查询模式
    where = ExamRecord.knowledge_base_id == knowledge_base_id if knowledge_base_id else None

    def _serialize(r: ExamRecord) -> dict:
        return {"id": r.id, "knowledge_base_id": r.knowledge_base_id, "question_type": r.question_type,
                "question_count": r.question_count, "difficulty": r.difficulty,
                "total_score": r.total_score, "max_score": r.max_score,
                "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None}

    result = await paginated_select(
        db, ExamRecord, page, page_size,
        where=where,
        order_by=ExamRecord.created_at.desc(),
        serializer=_serialize,
    )
    return APIResponse(data=result.model_dump())


@router.get("/records/{record_id}", response_model=APIResponse)
async def get_exam_record(record_id: int, db: AsyncSession = Depends(get_db)):
    record = await db.get(ExamRecord, record_id)
    if not record:
        raise NotFoundError("考试记录不存在")
    return APIResponse(data={
        "id": record.id, "knowledge_base_id": record.knowledge_base_id,
        "question_type": record.question_type, "question_count": record.question_count,
        "difficulty": record.difficulty, "questions": record.questions or [],
        "answers": record.answers or [], "scores": record.scores or [],
        "dimensions": record.dimensions, "total_score": record.total_score,
        "max_score": record.max_score, "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    })

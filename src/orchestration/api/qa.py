"""问答 API — 非流式 + SSE 流式。

变更 (Phase 1 P0-5): 通过 IGenerationService 门面调用，不再直接
import generation 内部模块。
"""
import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.mysql import get_db
from src.shared.models.orm import KnowledgeBase
from src.shared.models.orm import Feedback
from src.shared.models.schemas import APIResponse, QARequest, FeedbackCreate
from src.shared.exceptions import NotFoundError
from src.orchestration.services import get_generation_service
from src.orchestration.session import session_manager
from src.orchestration.pagination import paginate, get_offset_limit, paginated_select
from src.observability.retrieval_logger import retrieval_logger
from src.orchestration.middleware.metrics import QA_REQUESTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/qa", tags=["问答"])


async def _validate_kb(kb_id: int | None, db: AsyncSession):
    if kb_id is not None:
        kb = await db.get(KnowledgeBase, kb_id)
        if not kb:
            raise NotFoundError("知识库不存在")


@router.post("", response_model=APIResponse)
async def ask_question(req: QARequest, db: AsyncSession = Depends(get_db)):
    await _validate_kb(req.knowledge_base_id, db)

    # 多轮对话：构建完整上下文
    history = req.history or []
    if req.session_id:
        history = await session_manager.get_history(req.session_id, db) + history

    gen_svc = get_generation_service()
    try:
        result = await gen_svc.qa(
            question=req.question,
            knowledge_base_id=req.knowledge_base_id,
            top_k=req.top_k,
            use_rerank=req.use_rerank,
            history=history if history else None,
        )
        QA_REQUESTS.labels(
            knowledge_base_id=str(req.knowledge_base_id or "global"),
            status="ok",
        ).inc()
    except Exception:
        QA_REQUESTS.labels(
            knowledge_base_id=str(req.knowledge_base_id or "global"),
            status="error",
        ).inc()
        raise

    # 保存对话历史
    if req.session_id:
        await session_manager.append_message(req.session_id, "user", req.question, db)
        await session_manager.append_message(req.session_id, "assistant", result["answer"], db)
    result["session_id"] = req.session_id

    # Opt-8: 记录检索日志供离线评估
    try:
        await retrieval_logger.log(
            query=req.question,
            chunks=result.get("sources", []),
            answer=result.get("answer", ""),
            session_id=req.session_id,
        )
    except Exception:
        pass

    return APIResponse(data=result)


@router.post("/stream")
async def ask_question_stream(req: QARequest, db: AsyncSession = Depends(get_db)):
    await _validate_kb(req.knowledge_base_id, db)

    # 构建多轮对话上下文
    history = req.history or []
    if req.session_id:
        history = await session_manager.get_history(req.session_id, db) + history
        await session_manager.append_message(req.session_id, "user", req.question, db)

    gen_svc = get_generation_service()
    answer_buffer: list[str] = []

    async def generate():
        try:
            async for chunk in gen_svc.qa_stream(
                question=req.question,
                knowledge_base_id=req.knowledge_base_id,
                top_k=req.top_k,
                use_rerank=req.use_rerank,
                history=history if history else None,
            ):
                yield chunk
                # 提取纯文本（去掉 SSE 格式 "data: ...\n\n"），仅用于会话历史
                if chunk.startswith("data: ") and chunk.endswith("\n\n"):
                    inner = chunk[6:-2]
                    if inner != "[DONE]":
                        answer_buffer.append(inner)
            QA_REQUESTS.labels(
                knowledge_base_id=str(req.knowledge_base_id or "global"),
                status="ok",
            ).inc()
        except Exception:
            QA_REQUESTS.labels(
                knowledge_base_id=str(req.knowledge_base_id or "global"),
                status="error",
            ).inc()
            raise

        # 流式结束后持久化 assistant 回答
        if req.session_id:
            await session_manager.append_message(req.session_id, "assistant", "".join(answer_buffer), db)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── 用户反馈 (Phase 4 P3-4) ──

@router.post("/feedback", response_model=APIResponse)
async def submit_feedback(req: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    fb = Feedback(
        session_id=req.session_id,
        question=req.question,
        answer=req.answer,
        rating=req.rating,
        comment=req.comment,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    label = "👍 赞" if req.rating == 1 else "👎 踩"
    logger.info(f"feedback_submitted id={fb.id} rating={label}")
    return APIResponse(message="反馈提交成功", data={"id": fb.id})


@router.get("/feedback", response_model=APIResponse)
async def list_feedback(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # P2-2: 使用 paginated_select 消除重复的分页查询模式
    def _serialize(f: Feedback) -> dict:
        return {
            "id": f.id, "session_id": f.session_id, "question": f.question[:200],
            "answer": f.answer[:200], "rating": f.rating, "comment": f.comment,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }

    result = await paginated_select(
        db, Feedback, page, page_size,
        order_by=Feedback.created_at.desc(),
        serializer=_serialize,
    )
    return APIResponse(data=result.model_dump())

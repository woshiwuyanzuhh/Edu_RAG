"""知识库 API — CRUD + 分页。"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.mysql import get_db
from src.shared.models.orm import KnowledgeBase, Document
from src.shared.models.schemas import (
    APIResponse, KnowledgeBaseCreate, KnowledgeBaseUpdate,
)
from src.shared.exceptions import NotFoundError
from src.orchestration.pagination import paginate, get_offset_limit, paginated_select
from src.retrieval.vector_store import get_vector_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kb", tags=["知识库"])


@router.post("", response_model=APIResponse)
async def create_kb(req: KnowledgeBaseCreate, db: AsyncSession = Depends(get_db)):
    kb = KnowledgeBase(name=req.name, description=req.description, retrieval_config=req.retrieval_config)
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return APIResponse(message="知识库创建成功", data={"id": kb.id, "name": kb.name})


@router.get("", response_model=APIResponse)
async def list_kb(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # P2-2: 使用 paginated_select 消除重复的分页查询模式
    def _serialize(k: KnowledgeBase) -> dict:
        return {"id": k.id, "name": k.name, "description": k.description,
                "retrieval_config": k.retrieval_config,
                "created_at": k.created_at.isoformat() if k.created_at else None,
                "updated_at": k.updated_at.isoformat() if k.updated_at else None}

    result = await paginated_select(
        db, KnowledgeBase, page, page_size,
        order_by=KnowledgeBase.updated_at.desc(),
        serializer=_serialize,
    )
    return APIResponse(data=result.model_dump())


@router.get("/{kb_id}", response_model=APIResponse)
async def get_kb(kb_id: int, db: AsyncSession = Depends(get_db)):
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise NotFoundError("知识库不存在")
    return APIResponse(data={
        "id": kb.id, "name": kb.name, "description": kb.description,
        "retrieval_config": kb.retrieval_config,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
    })


@router.put("/{kb_id}", response_model=APIResponse)
async def update_kb(kb_id: int, req: KnowledgeBaseUpdate, db: AsyncSession = Depends(get_db)):
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise NotFoundError("知识库不存在")
    if req.name is not None:
        kb.name = req.name
    if req.description is not None:
        kb.description = req.description
    if req.retrieval_config is not None:
        kb.retrieval_config = req.retrieval_config
    await db.commit()
    return APIResponse(message="知识库更新成功")


@router.delete("/{kb_id}", response_model=APIResponse)
async def delete_kb(kb_id: int, db: AsyncSession = Depends(get_db)):
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise NotFoundError("知识库不存在")

    # 级联删除
    vector_store = get_vector_store()

    # 删除向量
    try:
        await vector_store.delete_by_filter({"knowledge_base_id": kb_id})
    except Exception as e:
        logger.warning(f"vector_delete_failed kb_id={kb_id} error={e}")

    # 删除物理文件 — P2: asyncio.to_thread 避免阻塞事件循环
    import os
    import asyncio
    docs_result = await db.execute(select(Document).where(Document.knowledge_base_id == kb_id))
    for doc in docs_result.scalars():
        if os.path.exists(doc.file_path):
            await asyncio.to_thread(os.remove, doc.file_path)

    await db.delete(kb)
    await db.commit()
    logger.info(f"kb_deleted kb_id={kb_id}")
    return APIResponse(message="知识库及关联数据已删除")

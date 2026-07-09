"""文档 API — 上传/列表/删除。

变更 (Phase 1 P0-5): 通过 IIngestionService 门面调用，不再直接
import ingress/retrieval 内部模块。
"""
import os
import uuid
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import settings
from src.shared.database.mysql import get_db
from src.shared.models.orm import Document, KnowledgeBase
from src.shared.models.schemas import APIResponse
from src.shared.exceptions import NotFoundError, UnsupportedFileType, FileTooLarge
from src.orchestration.pagination import paginate, get_offset_limit
from src.orchestration.services import get_ingestion_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["文档"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc", ".md"}


@router.post("/upload", response_model=APIResponse)
async def upload_document(
    file: UploadFile = File(...),
    knowledge_base_id: int = Form(...),
    doc_type: str = Form(default="general"),
    db: AsyncSession = Depends(get_db),
):
    # 1. 校验知识库
    kb = await db.get(KnowledgeBase, knowledge_base_id)
    if not kb:
        raise NotFoundError("知识库不存在")

    # 2. 安全文件名
    raw_name = file.filename or "unknown"
    safe_filename = Path(raw_name).name
    if not safe_filename or safe_filename == ".":
        raise UnsupportedFileType("无效的文件名")

    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(f"不支持的文件类型: {ext}")

    # 3. 校验大小
    content = await file.read()
    max_bytes = settings.app.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise FileTooLarge(f"文件大小超过 {settings.app.max_upload_size_mb}MB 限制")

    # 4. 保存文件
    upload_dir = settings.app.get_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{knowledge_base_id}_{ts}_{uuid.uuid4().hex[:8]}_{safe_filename}"
    file_path = os.path.join(upload_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    # 5. 创建记录
    doc = Document(
        filename=safe_filename,
        file_path=file_path,
        file_type=ext.lstrip("."),
        file_size=len(content),
        knowledge_base_id=knowledge_base_id,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # 6. 写入管线 — 通过 IIngestionService 门面（P0-5）
    try:
        ingestion_svc = get_ingestion_service()
        result = await ingestion_svc.ingest(
            file_path=file_path, doc_id=doc.id, kb_id=knowledge_base_id, doc_type=doc_type,
            chunk_size=settings.ingress_cfg.chunk_size,
            chunk_overlap=settings.ingress_cfg.chunk_overlap,
        )

        doc.chunk_count = result.chunk_count
        doc.status = "done"
        await db.commit()

        return APIResponse(
            message=f"文档上传成功，共 {doc.chunk_count} 个片段",
            data={"doc_id": doc.id, "chunk_count": doc.chunk_count},
        )

    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        await db.commit()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise


@router.get("", response_model=APIResponse)
async def list_documents(
    knowledge_base_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Document)
    count_query = select(func.count(Document.id))
    if knowledge_base_id:
        query = query.where(Document.knowledge_base_id == knowledge_base_id)
        count_query = count_query.where(Document.knowledge_base_id == knowledge_base_id)

    total = (await db.execute(count_query)).scalar() or 0
    offset, limit = get_offset_limit(page, page_size)
    result = await db.execute(query.order_by(Document.created_at.desc()).offset(offset).limit(limit))
    docs = result.scalars().all()

    items = [{"id": d.id, "filename": d.filename, "file_type": d.file_type, "file_size": d.file_size,
              "knowledge_base_id": d.knowledge_base_id, "chunk_count": d.chunk_count,
              "status": d.status, "created_at": d.created_at.isoformat() if d.created_at else None} for d in docs]
    return APIResponse(data=paginate(items, total, page, page_size).model_dump())


@router.delete("/{doc_id}", response_model=APIResponse)
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise NotFoundError("文档不存在")

    kb_id = doc.knowledge_base_id

    # 通过门面删除向量 + 物理文件（P0-7：不在 API 层硬编码 range）
    try:
        ingestion_svc = get_ingestion_service()
        await ingestion_svc.delete_document(doc_id=doc_id, kb_id=kb_id, file_path=doc.file_path)
    except Exception:
        logger.warning(f"ingestion_delete_failed doc_id={doc_id}")

    await db.delete(doc)
    await db.commit()

    return APIResponse(message="文档已删除")

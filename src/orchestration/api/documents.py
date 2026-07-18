"""文档 API — 上传/列表/删除。

变更 (Phase 1 P0-5): 通过 IIngestionService 门面调用，不再直接
import ingress/retrieval 内部模块。
"""
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import settings
from src.shared.database.mysql import get_db
from src.shared.models.orm import Document, KnowledgeBase
from src.shared.models.schemas import APIResponse
from src.shared.exceptions import NotFoundError, UnsupportedFileType, FileTooLarge
from src.orchestration.pagination import paginate, get_offset_limit, paginated_select
from src.orchestration.jobs.ingestion import delete_document_resources, process_document_ingestion
from src.orchestration.middleware.metrics import DOCUMENT_PROCESSED

router = APIRouter(prefix="/api/documents", tags=["文档"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc", ".md"}

# P2-9: 文件魔数校验（纯 Python，不依赖 python-magic，避免 Windows libmagic 依赖问题）
_FILE_MAGIC: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".docx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],  # Office Open XML (ZIP)
    ".doc": [b"\xd0\xcf\x11\xe0"],  # OLE2 复合文档
    # .txt / .md 无固定魔数，跳过校验
}


def _validate_file_magic(header: bytes, ext: str) -> None:
    """P2-9: 校验文件头魔数，防止伪造扩展名绕过。"""
    magics = _FILE_MAGIC.get(ext.lower())
    if not magics:
        return  # 无魔数定义的类型（txt/md）跳过
    if not any(header.startswith(m) for m in magics):
        raise UnsupportedFileType(f"文件内容与扩展名 {ext} 不匹配（魔数校验失败）")


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

    # 3. 分块读取 + 写盘 + 大小校验（P2-4: aiofiles 分块写盘，避免全量读入内存）
    import aiofiles
    max_bytes = settings.app.max_upload_size_mb * 1024 * 1024
    upload_dir = settings.app.get_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{knowledge_base_id}_{ts}_{uuid.uuid4().hex[:8]}_{safe_filename}"
    file_path = os.path.join(upload_dir, safe_name)

    total_size = 0
    file_header = b""
    _chunk_size = 1024 * 1024  # 1MB 分块

    async with aiofiles.open(file_path, "wb") as f:
        while True:
            chunk = await file.read(_chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_bytes:
                await f.close()
                os.remove(file_path)
                raise FileTooLarge(f"文件大小超过 {settings.app.max_upload_size_mb}MB 限制")
            if not file_header:
                file_header = chunk[:16]  # 保存文件头用于魔数校验
            await f.write(chunk)

    # P2-9: 魔数校验 — 防止伪造扩展名
    _validate_file_magic(file_header, ext)

    # P1-D2: 存储抽象 — 本地无变化，对象存储上传后 file_path 改为 s3:// URI
    from src.shared.storage import get_storage
    storage_key = await get_storage().save(file_path, safe_name)

    # 5. 创建记录
    doc = Document(
        filename=safe_filename,
        file_path=storage_key,
        file_type=ext.lstrip("."),
        file_size=total_size,
        knowledge_base_id=knowledge_base_id,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # 6. 写入管线 — P1-C5: 异步队列投递（生产）或同步处理（开发/兜底）
    if settings.app.async_ingestion:
        from src.orchestration.worker.client import enqueue_ingestion
        if await enqueue_ingestion(
            doc_id=doc.id, kb_id=knowledge_base_id, doc_type=doc_type,
        ):
            return APIResponse(
                message="文档已上传，正在后台处理",
                data={"doc_id": doc.id, "status": "processing"},
            )
        logging.getLogger(__name__).warning(f"arq_unavailable_fallback_sync doc_id={doc.id}")

    chunk_count = await process_document_ingestion(
        db=db,
        document=doc,
        knowledge_base_id=knowledge_base_id,
        doc_type=doc_type,
    )
    DOCUMENT_PROCESSED.labels(status="ok").inc()

    return APIResponse(
        message=f"文档上传成功，共 {chunk_count} 个片段",
        data={"doc_id": doc.id, "chunk_count": chunk_count},
    )


@router.get("", response_model=APIResponse)
async def list_documents(
    knowledge_base_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # P2-2: 使用 paginated_select 消除重复的分页查询模式
    where = Document.knowledge_base_id == knowledge_base_id if knowledge_base_id else None

    def _serialize(d: Document) -> dict:
        return {"id": d.id, "filename": d.filename, "file_type": d.file_type, "file_size": d.file_size,
                "knowledge_base_id": d.knowledge_base_id, "chunk_count": d.chunk_count,
                "status": d.status, "created_at": d.created_at.isoformat() if d.created_at else None}

    result = await paginated_select(
        db, Document, page, page_size,
        where=where,
        order_by=Document.created_at.desc(),
        serializer=_serialize,
    )
    return APIResponse(data=result.model_dump())


@router.delete("/{doc_id}", response_model=APIResponse)
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise NotFoundError("文档不存在")

    kb_id = doc.knowledge_base_id

    # P1-D2: 删除存储文件（本地/对象存储统一）
    # 注：对象存储部署时，ingestion service 的文件删除需适配 s3:// URI（当前 LocalStorage 兼容）
    from src.shared.storage import get_storage
    await get_storage().delete(doc.file_path)

    # 通过 orchestration job 删除向量 + 物理文件
    await delete_document_resources(doc_id=doc_id, kb_id=kb_id, file_path=doc.file_path)

    await db.delete(doc)
    await db.commit()

    return APIResponse(message="文档已删除")

"""
Ingestion 管线 — parse → clean → chunk → filter 完整流程。

解决问题 #5 (分块决定检索上限):
    - 每块附加元数据 (doc_id, kb_id, chunk_index, source_file)
    - 块大小/重叠度可通过配置调整
"""
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field

from src.ingress.parsers import PARSER_REGISTRY
from src.ingress.cleaners import CLEANER_REGISTRY
from src.ingress.chunkers import RecursiveChunker
from src.interfaces.parser import IParser
from src.interfaces.cleaner import ICleaner
from src.interfaces.chunker import IChunker
from src.shared.exceptions import UnsupportedFileType, EmptyDocumentError

logger = logging.getLogger(__name__)


@dataclass
class ChunkWithMeta:
    """带元数据的文本块。"""
    text: str
    doc_id: int = 0
    kb_id: int = 0
    chunk_index: int = 0
    source_file: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class IngestionResult:
    """写入管线结果。"""
    chunks: list[ChunkWithMeta]
    total_chars: int = 0
    original_chars: int = 0
    stats: dict = field(default_factory=dict)


async def run_ingestion(
    file_path: str,
    doc_id: int,
    kb_id: int,
    doc_type: str = "general",
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> IngestionResult:
    """执行完整的文档写入管线。

    Args:
        file_path: 文件路径
        doc_id: 文档 ID（MySQL 中的记录）
        kb_id: 知识库 ID
        doc_type: 文档类型 (general / education / gaming)
        chunk_size: 目标块大小
        chunk_overlap: 块间重叠

    Returns:
        IngestionResult: 包含所有 chunk 和统计信息

    Raises:
        UnsupportedFileType: 不支持的文件类型
        EmptyDocumentError: 解析后无有效内容
    """
    logger.info(f"ingestion_start file={file_path} doc_id={doc_id} kb_id={kb_id} doc_type={doc_type}")

    # 1. 选择解析器
    ext = Path(file_path).suffix.lower()
    parser: IParser | None = PARSER_REGISTRY.get(ext)
    if parser is None:
        supported = list(PARSER_REGISTRY.keys())
        raise UnsupportedFileType(f"不支持的文件类型: {ext}，支持: {supported}")

    # 2. 解析（to_thread 避免阻塞事件循环）
    raw_text = await asyncio.to_thread(parser.parse, file_path)
    original_chars = len(raw_text)
    if not raw_text:
        raise EmptyDocumentError("文档解析后无内容")

    # 3. 选择清洗器
    cleaner: ICleaner = CLEANER_REGISTRY.get(doc_type, CLEANER_REGISTRY["general"])

    # 4. 清洗（to_thread 避免阻塞事件循环）
    cleaned_text = await asyncio.to_thread(cleaner.clean, raw_text)

    # 5. 切分（to_thread 避免阻塞事件循环）
    chunker: IChunker = RecursiveChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    raw_chunks = await asyncio.to_thread(chunker.split, cleaned_text)

    # 6. 过滤
    filtered_chunks = cleaner.filter_chunks(raw_chunks)

    # 7. 附加元数据
    chunks_with_meta = []
    for i, text in enumerate(filtered_chunks):
        chunks_with_meta.append(ChunkWithMeta(
            text=text,
            doc_id=doc_id,
            kb_id=kb_id,
            chunk_index=i,
            source_file=Path(file_path).name,
            metadata={
                "doc_type": doc_type,
                "char_count": len(text),
            },
        ))

    total_chars = sum(len(c.text) for c in chunks_with_meta)
    stats = {
        "original_chars": original_chars,
        "cleaned_chars": len(cleaned_text),
        "raw_chunks": len(raw_chunks),
        "filtered_chunks": len(filtered_chunks),
        "reduction_ratio": round((1 - len(filtered_chunks) / max(len(raw_chunks), 1)) * 100, 1),
    }

    logger.info(f"ingestion_complete stats={stats}")
    return IngestionResult(chunks=chunks_with_meta, total_chars=total_chars, original_chars=original_chars, stats=stats)

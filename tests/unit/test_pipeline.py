"""写入管线测试 — src/ingress/pipeline.py。"""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ingress.pipeline import run_ingestion, ChunkWithMeta, IngestionResult
from src.shared.exceptions import UnsupportedFileType, EmptyDocumentError


class TestIngestionResult:
    """IngestionResult 数据类。"""

    def test_defaults(self):
        chunk = ChunkWithMeta(text="测试文本", doc_id=1, kb_id=1, chunk_index=0, source_file="test.pdf")
        result = IngestionResult(chunks=[chunk], total_chars=4, original_chars=4)
        assert result.total_chars == 4
        assert result.original_chars == 4
        assert result.stats == {}

    def test_with_stats(self):
        chunk = ChunkWithMeta(text="ABC")
        result = IngestionResult(
            chunks=[chunk], total_chars=3, original_chars=5,
            stats={"reduction_ratio": 40.0}
        )
        assert result.stats["reduction_ratio"] == 40.0


class TestChunkWithMeta:
    """ChunkWithMeta 数据类。"""

    def test_default_metadata(self):
        chunk = ChunkWithMeta(text="内容")
        assert chunk.metadata == {}
        assert chunk.doc_id == 0
        assert chunk.kb_id == 0
        assert chunk.chunk_index == 0
        assert chunk.source_file == ""

    def test_full_metadata(self):
        chunk = ChunkWithMeta(
            text="完整内容",
            doc_id=42,
            kb_id=7,
            chunk_index=3,
            source_file="test.pdf",
            metadata={"doc_type": "education", "char_count": 4},
        )
        assert chunk.doc_id == 42
        assert chunk.kb_id == 7
        assert chunk.chunk_index == 3
        assert chunk.source_file == "test.pdf"
        assert chunk.metadata["doc_type"] == "education"


class TestRunIngestionErrors:
    """run_ingestion 异常路径。"""

    def test_unsupported_extension(self):
        with pytest.raises(UnsupportedFileType):
            asyncio.run(run_ingestion(
                file_path="test.xyz",
                doc_id=1,
                kb_id=1,
            ))

    def test_empty_file_after_parse(self):
        """解析后文本为空应抛出 EmptyDocumentError。"""
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("")
            tmp_path = f.name

        try:
            with pytest.raises(EmptyDocumentError):
                asyncio.run(run_ingestion(
                    file_path=tmp_path,
                    doc_id=1,
                    kb_id=1,
                ))
        finally:
            os.unlink(tmp_path)


class TestRunIngestionSuccess:
    """run_ingestion 正常流程。"""

    def test_txt_file_ingestion(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("这是第一段测试内容，用于验证写入管线。\n\n这是第二段内容，包含足够长度的中文文本用于分块测试。")
            tmp_path = f.name

        try:
            result = asyncio.run(run_ingestion(
                file_path=tmp_path,
                doc_id=1,
                kb_id=1,
                chunk_size=50,
                chunk_overlap=5,
            ))
            assert isinstance(result, IngestionResult)
            assert len(result.chunks) >= 1
            assert result.original_chars > 0
            assert result.total_chars > 0
            # 验证每个 chunk 都有元数据
            for chunk in result.chunks:
                assert chunk.doc_id == 1
                assert chunk.kb_id == 1
                assert chunk.source_file == Path(tmp_path).name
                assert "doc_type" in chunk.metadata
                assert "char_count" in chunk.metadata
                assert chunk.metadata["char_count"] == len(chunk.text)
            # 验证统计信息
            assert "original_chars" in result.stats
            assert "cleaned_chars" in result.stats
            assert "raw_chunks" in result.stats
            assert "filtered_chunks" in result.stats
            assert "reduction_ratio" in result.stats
        finally:
            os.unlink(tmp_path)

    def test_txt_with_chinese_content(self):
        """中文长文本应被正确分块。"""
        content = "人工智能是计算机科学的一个重要分支。\n\n" * 50
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp_path = f.name

        try:
            result = asyncio.run(run_ingestion(
                file_path=tmp_path,
                doc_id=2,
                kb_id=2,
                chunk_size=200,
                chunk_overlap=20,
            ))
            # 长文本至少产生 1 个 chunk
            assert len(result.chunks) >= 1
            # 每个 chunk 不应超过 chunk_size
            for chunk in result.chunks:
                assert len(chunk.text) <= 200
        finally:
            os.unlink(tmp_path)

    def test_different_doc_types(self):
        """验证 doc_type 参数正确传递给清洗器。"""
        content = "这是教育相关的测试内容。" * 30
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp_path = f.name

        try:
            for doc_type in ["general", "education", "gaming"]:
                result = asyncio.run(run_ingestion(
                    file_path=tmp_path,
                    doc_id=1,
                    kb_id=1,
                    doc_type=doc_type,
                    chunk_size=200,
                ))
                for chunk in result.chunks:
                    assert chunk.metadata["doc_type"] == doc_type
        finally:
            os.unlink(tmp_path)

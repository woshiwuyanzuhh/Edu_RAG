"""PDF 解析器 — PyMuPDF + pikepdf 兜底解密。

鲁棒性策略（按优先级）：
    1. PyMuPDF 直接打开
    2. 检测加密：尝试空密码认证（owner-password 场景，用户无感知）
    3. 检测损坏：page_count == 0 或 is_dirty，用 pikepdf 修复并重新打开
    4. 加密但无密码可解 → 抛 ParseError 给出明确提示
"""

import io
import logging
from contextlib import redirect_stderr

import fitz  # PyMuPDF

from src.interfaces.parser import IParser
from src.shared.exceptions import ParseError

logger = logging.getLogger(__name__)


class PDFParser(IParser):
    @property
    def supported_extensions(self) -> set[str]:
        return {".pdf"}

    def parse(self, file_path: str) -> str:
        # 捕获 MuPDF 的 stderr 警告（默认直接打到 stderr，不会进 logger）
        mupdf_warnings: list[str] = []
        try:
            with redirect_stderr(io.StringIO()) as buf:
                text = self._parse_with_recovery(file_path)
                mupdf_warnings = [line for line in buf.getvalue().splitlines() if line.strip()]
        except _EncryptedPDFError:
            # 加密但无法解锁 — 给用户明确提示
            raise ParseError(
                f"PDF 已加密，无法解析: {file_path}",
                detail=(
                    "该 PDF 设置了用户密码（user password），程序无法提取文本。"
                    "请在本地用 PDF 阅读器打开后，通过「打印 → 另存为 PDF」或"
                    "「另存为」生成未加密版本后重新上传。"
                ),
            )
        except Exception as e:
            detail = str(e)
            if mupdf_warnings:
                detail = f"MuPDF 警告: {'; '.join(mupdf_warnings)} | 原始错误: {detail}"
            raise ParseError(f"PDF 解析失败: {file_path}", detail=detail)

        if mupdf_warnings:
            logger.warning(f"pdf_parse_warnings file={file_path} warnings={mupdf_warnings[:3]}")
        return text

    def _parse_with_recovery(self, file_path: str) -> str:
        """带恢复逻辑的 PDF 解析。"""
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            # PyMuPDF 打开异常 → 尝试 pikepdf 修复
            logger.info(f"fitz_open_failed, trying pikepdf recovery: {e}")
            return self._parse_via_pikepdf(file_path, password="")

        try:
            # 检测加密
            if doc.is_encrypted:
                # 尝试空密码认证（owner-password 场景：用户能打开看，但程序没密码）
                if not doc.authenticate(""):
                    logger.warning(f"pdf_encrypted_no_password file={file_path}")
                    raise _EncryptedPDFError(file_path)
                logger.info(f"pdf_decrypted_with_empty_password file={file_path}")

            # 检测 page_count == 0（可能是损坏的对象流）
            if doc.page_count == 0:
                logger.warning(f"pdf_zero_pages_recovering file={file_path} is_dirty={doc.is_dirty}")
                doc.close()
                return self._parse_via_pikepdf(file_path, password="")

            # 正常提取
            text_parts = []
            for page in doc:
                try:
                    text_parts.append(page.get_text())
                except Exception as e:
                    logger.debug(f"page_extract_failed, skipped: {e}")
                    text_parts.append("")
            return "\n\n".join(text_parts).strip()
        finally:
            try:
                doc.close()
            except Exception:
                pass

    def _parse_via_pikepdf(self, file_path: str, password: str) -> str:
        """用 pikepdf 修复/解密后重新用 PyMuPDF 提取文本。

        pikepdf 基于 QPDF，对损坏/加密 PDF 的容错能力强于 PyMuPDF。
        修复后的 PDF 写入内存，再交给 PyMuPDF 提取文本（保留排版信息）。
        """
        try:
            import pikepdf
        except ImportError:
            raise ParseError(
                "PDF 修复需要 pikepdf 库，但未安装",
                detail="请在容器内执行: pip install pikepdf",
            )

        try:
            with pikepdf.open(file_path, password=password) as pdf:
                # 保存为未加密、清理后的 PDF 到内存
                buf = io.BytesIO()
                pdf.save(buf, fix_metadata_version=True)
                buf.seek(0)
        except pikepdf.PasswordError:
            # 密码错误 → 加密 PDF 无法解锁
            raise _EncryptedPDFError(file_path)
        except Exception as e:
            raise ParseError(
                f"pikepdf 修复失败: {file_path}",
                detail=str(e),
            )

        # 用修复后的 PDF 重新提取文本
        data = buf.getvalue()
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            if doc.page_count == 0:
                raise ParseError(
                    f"PDF 修复后仍无页面: {file_path}",
                    detail="PDF 文件严重损坏，所有解析库均无法识别页面结构",
                )
            text_parts = []
            for page in doc:
                try:
                    text_parts.append(page.get_text())
                except Exception:
                    text_parts.append("")
            return "\n\n".join(text_parts).strip()
        finally:
            doc.close()


class _EncryptedPDFError(Exception):
    """内部异常：PDF 加密且无法用空密码解锁。"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        super().__init__(f"encrypted_pdf: {file_path}")

"""BM25 关键词检索 — 用于混合检索（向量 + 关键词）的双路召回。

使用 rank_bm25 库（纯 Python，零外部依赖）。中文需外层分词，此处使用简单字符级 n-gram。

P2-6 优化: 增删操作标记 dirty 延迟重建，避免每次 add/remove 都 O(n) 重建 BM25Okapi。
"""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# 延迟导入避免强制依赖
try:
    from rank_bm25 import BM25Okapi

    _HAS_BM25 = True
except ImportError:
    BM25Okapi = None  # type: ignore
    _HAS_BM25 = False


def _simple_tokenize(text: str) -> list[str]:
    """简单分词 — 按字符 bigram 分割（适合中文）。

    英文按空格分词，中文按 bigram 切分。
    """
    tokens: list[str] = []
    # 按空格/标点粗略分
    import re

    segments = re.split(r"[\s,，。！？；;：:]+", text)
    for seg in segments:
        if not seg:
            continue
        # ASCII 片段按空格分词
        if all(ord(c) < 128 for c in seg):
            tokens.extend(seg.lower().split())
        else:
            # 中文字符级 bigram
            for i in range(len(seg) - 1):
                tokens.append(seg[i : i + 2])
            if len(seg) == 1:
                tokens.append(seg)
    return tokens


class BM25Index:
    """BM25 关键词索引 — 封装 rank_bm25.BM25Okapi。

    用法:
        idx = BM25Index()
        idx.build(["文档1文本", "文档2文本", "文档3文本"])
        results = idx.search("查询关键词", top_k=5)
        # → [(doc_index, score), ...]

    索引维护:
        idx.add("新文档文本")
        idx.remove(0)  # 删除第 0 号文档
        idx.rebuild(all_docs)  # 全量重建

    P2-6: add/remove 标记 dirty 延迟重建，批量操作后只在 search 时重建一次。
    """

    def __init__(self):
        if not _HAS_BM25:
            raise ImportError("rank_bm25 未安装。请执行: pip install rank-bm25")
        self._bm25: Any = None
        self._docs: list[str] = []
        self._metadatas: list[dict] = []
        self._tokenized: list[list[str]] = []
        self._dirty: bool = False  # P2-6: 延迟重建标志

    @property
    def doc_count(self) -> int:
        return len(self._docs)

    def _rebuild(self) -> None:
        """P2-6: 延迟重建 BM25 索引（仅在有变更时调用）。"""
        if self._tokenized:
            self._bm25 = BM25Okapi(self._tokenized)
        else:
            self._bm25 = None
        self._dirty = False

    def build(self, documents: list[str], metadatas: list[dict] | None = None) -> None:
        """全量构建索引。"""
        self._docs = list(documents)
        self._metadatas = list(metadatas or [{} for _ in documents])
        if len(self._metadatas) != len(self._docs):
            raise ValueError("metadatas length must match documents length")
        self._tokenized = [_simple_tokenize(d) for d in self._docs]
        self._rebuild()

    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        """搜索，返回 [(doc_index, score), ...] 按 score 降序。"""
        # P2-6: 延迟重建 — 只在搜索时重建脏索引，避免批量增删时多次 O(n) 重建
        if self._dirty:
            self._rebuild()
        if not self._bm25 or not self._docs:
            return []
        tokens = _simple_tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        # 按 score 降序，取 top_k
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in indexed[:top_k] if s > 0]

    def add(self, document: str, metadata: dict | None = None) -> int:
        """追加文档，返回新索引位置（P2-6: 延迟重建）。"""
        idx = len(self._docs)
        self._docs.append(document)
        self._metadatas.append(metadata or {})
        self._tokenized.append(_simple_tokenize(document))
        self._dirty = True  # 标记脏，延迟到 search 时重建
        return idx

    def remove(self, doc_index: int) -> None:
        """删除指定索引的文档（P2-6: 延迟重建）。"""
        if 0 <= doc_index < len(self._docs):
            del self._docs[doc_index]
            del self._metadatas[doc_index]
            del self._tokenized[doc_index]
            self._dirty = True  # 标记脏，延迟到 search 时重建

    def remove_where(self, predicate: Callable[[dict], bool]) -> int:
        """删除满足元数据条件的文档，返回删除数量（P2-6: 延迟重建）。"""
        keep_docs: list[str] = []
        keep_metadatas: list[dict] = []
        removed = 0
        for doc, metadata in zip(self._docs, self._metadatas, strict=True):
            if predicate(metadata):
                removed += 1
            else:
                keep_docs.append(doc)
                keep_metadatas.append(metadata)
        if removed:
            self._docs = keep_docs
            self._metadatas = keep_metadatas
            self._tokenized = [_simple_tokenize(d) for d in self._docs]
            self._dirty = True  # 标记脏，延迟到 search 时重建
        return removed

    def get_document(self, doc_index: int) -> str:
        """按 BM25 内部索引返回文本。"""
        return self._docs[doc_index]

    def get_metadata(self, doc_index: int) -> dict:
        """按 BM25 内部索引返回元数据。"""
        return self._metadatas[doc_index]

    def rebuild(self, documents: list[str], metadatas: list[dict] | None = None) -> None:
        """全量重建（用于批量同步）。"""
        self.build(documents, metadatas)

    # ── P0-C3: 持久化支持 ──

    def to_state(self) -> dict:
        """导出可持久化状态（仅 docs + metadatas，tokenized/bm25 可重建）。"""
        return {"docs": list(self._docs), "metadatas": list(self._metadatas)}

    def from_state(self, state: dict) -> None:
        """从持久化状态加载并重建索引。"""
        self._docs = list(state.get("docs", []))
        self._metadatas = list(state.get("metadatas", []))
        if len(self._metadatas) != len(self._docs):
            raise ValueError("metadatas length must match docs length")
        self._tokenized = [_simple_tokenize(d) for d in self._docs]
        self._rebuild()

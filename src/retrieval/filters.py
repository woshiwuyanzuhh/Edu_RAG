"""
检索过滤器 — 去重、压缩、上下文构建。

解决问题 #12: "Lost in the Middle" 策略真正重排 —
    最高分放头部（最相关），次高分放尾部，低分居中。

解决问题 #7: 上下文质量优先于上下文长度 —
    去重、过滤低分、压缩冗余。
"""
import logging
from src.shared.config import settings
from src.interfaces.vector_store import SearchResult

logger = logging.getLogger(__name__)


def filter_by_score(hits: list[SearchResult], min_score: float | None = None) -> list[SearchResult]:
    if min_score is None:
        min_score = settings.retrieval.min_score
    """过滤低分结果。"""
    return [h for h in hits if h.score >= min_score]


def deduplicate_by_text(hits: list[SearchResult], prefix_len: int = 120) -> list[SearchResult]:
    """按文本前缀去重。"""
    seen: set[str] = set()
    result = []
    for h in hits:
        key = (h.text or "")[:prefix_len]
        if key not in seen:
            seen.add(key)
            result.append(h)
    return result


def lost_in_middle_reorder(hits: list[SearchResult]) -> list[SearchResult]:
    """"Lost in the Middle" 上下文重排。

    ⚠️ DEPRECATED (Opt-11): 此实现已迁移至 generation/context/lost_middle.py。
    新代码请使用 ContextPipeline + LostInMiddleReorder。
    此函数保留仅用于 backward compatibility（retrieve_with_context 旧路径）。
    """
    if len(hits) <= 3:
        return hits

    # hits 已是按 score 降序
    best = hits[0]
    second_best = hits[1]
    middle = sorted(hits[2:], key=lambda x: x.score, reverse=True)

    return [best] + middle + [second_best]


def build_context(
    hits: list[SearchResult],
    min_score: float | None = None,
    max_chunks: int | None = None,
    reorder: bool = True,
) -> str:
    """将检索结果拼接为 LLM 上下文。

    Args:
        hits: 检索结果
        min_score: 最低分数阈值
        max_chunks: 最多保留的块数
        reorder: 是否启用 Lost in the Middle 重排

    Returns:
        格式化的上下文字符串
    """
    # 1. 过滤低分
    _min_score = min_score if min_score is not None else settings.retrieval.min_score
    _max_chunks = max_chunks if max_chunks is not None else settings.retrieval.max_chunks
    filtered = filter_by_score(hits, _min_score)

    # 2. 去重
    filtered = deduplicate_by_text(filtered)

    # 3. 限制数量
    filtered = filtered[:_max_chunks]

    if not filtered:
        return ""

    # 4. Lost in the Middle 重排
    if reorder and len(filtered) > 3:
        filtered = lost_in_middle_reorder(filtered)

    # 5. 拼接
    parts = []
    for i, h in enumerate(filtered):
        doc_label = h.metadata.get("source_file", h.metadata.get("doc_id", "?"))
        pos = ""
        if reorder and len(filtered) > 3:
            if i == 0:
                pos = "（最相关）"
            elif i == len(filtered) - 1:
                pos = "（次相关）"
        parts.append(f"【片段{i + 1}】{pos}(来源: {doc_label})\n{h.text}")

    logger.debug(f"build_context total={len(hits)} filtered={len(filtered)} reorder={reorder}")
    return "\n\n---\n\n".join(parts)

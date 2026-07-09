"""检索服务实现 — 封装 recall + rerank + build_context 完整管线。

解决问题：
    - 架构原则 #4: 检索与生成解耦，Generation 层只依赖 IRetrievalService 接口
    - 消除 exam_engine / qa_engine 对 retrieval 内部模块的直接 import
"""
import asyncio
import logging

from src.shared.config import settings
from src.interfaces.retrieval_service import IRetrievalService
from src.observability.decorators import traced
from src.interfaces.embedder import IEmbedder
from src.interfaces.vector_store import IVectorStore, SearchResult
from src.interfaces.llm import ILLMClient
from src.interfaces.query_expander import IQueryExpander
from src.retrieval.recall import recall
from src.retrieval.rerank import llm_rerank
from src.retrieval.filters import build_context, deduplicate_by_text
from src.retrieval.query.expander import LLMQueryExpander
from src.retrieval.keyword import get_bm25, build_bm25 as build_bm25_index
from src.observability import Tracer

logger = logging.getLogger(__name__)


class RetrievalService(IRetrievalService):
    """检索服务 — 依赖注入 Embedder + VectorStore + 可选 LLMClient（用于 rerank/expand）。

    用法:
        svc = RetrievalService(embedder=get_embedder(), vector_store=get_vector_store(), llm_client=llm)
        hits = await svc.retrieve("什么是RAG", knowledge_base_id=1)
        ctx  = await svc.build_context_for_exam(knowledge_base_id=1)
    """

    def __init__(
        self,
        embedder: IEmbedder,
        vector_store: IVectorStore,
        llm_client: ILLMClient | None = None,
    ):
        self._embedder = embedder
        self._vector_store = vector_store
        self._llm_client = llm_client
        # expander 在需要时惰性创建；BM25 索引通过全局单例共享（由 ingestion 构建）
        self._expander: IQueryExpander | None = None

    def _get_expander(self) -> IQueryExpander | None:
        if self._expander is None and self._llm_client is not None:
            self._expander = LLMQueryExpander(self._llm_client)
        return self._expander

    async def build_bm25(self, documents: list[str]) -> None:
        """构建共享 BM25 关键词索引 — 供混合检索使用。

        应在文档上传成功后调用，确保 BM25 索引与向量库同步。
        """
        import logging
        log = logging.getLogger(__name__)
        idx = build_bm25_index(documents)
        if idx is not None:
            log.info(f"bm25_built doc_count={idx.doc_count}")
        else:
            log.warning("bm25_build_skipped — rank_bm25 未安装")

    # ── IRetrievalService 实现 ──

    @traced("retrieval.retrieve")
    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: int | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
        hybrid: bool = False,
    ) -> list[SearchResult]:
        tracer = Tracer(query=query)

        # 1. 向量召回
        expander = self._get_expander()
        async with tracer.span("recall") as span:
            vec_hits = await recall(
                query=query,
                embedder=self._embedder,
                vector_store=self._vector_store,
                expander=expander,
                top_k=top_k * 2 if use_rerank else top_k,
                knowledge_base_id=knowledge_base_id,
                recall_multiplier=settings.retrieval.recall_multiplier,
            )
            span.metadata["vec_hit_count"] = len(vec_hits)

        # 2. 混合检索：BM25 关键词召回 + RRF 融合
        if hybrid and self._hybrid_ready():
            async with tracer.span("keyword") as span:
                bm25 = get_bm25()
                kw_results = await asyncio.to_thread(
                    bm25.search, query, top_k=max(top_k * 2, 10)
                )
                # 映射 BM25 结果到 SearchResult
                kw_hits = [
                    SearchResult(
                        id=f"kw_{idx}", text=bm25._docs[idx],
                        score=score / max(s for _, s in kw_results) if kw_results else 0,
                        metadata={"source": "bm25", "doc_index": idx},
                    )
                    for idx, score in kw_results
                ]
                span.metadata["kw_hit_count"] = len(kw_hits)
            vec_hits = self._rrf_fuse(vec_hits, kw_hits)

        if not vec_hits:
            tracer.log_report()
            return []

        # 3. 精排重排（可选）
        if use_rerank and self._llm_client and len(vec_hits) > top_k:
            async with tracer.span("rerank") as span:
                vec_hits = await llm_rerank(
                    query=query,
                    candidates=vec_hits,
                    llm_client=self._llm_client,
                    top_k=top_k,
                )
                span.metadata["final_count"] = len(vec_hits)

        tracer.log_report()
        return vec_hits

    def _hybrid_ready(self) -> bool:
        """检查 BM25 索引是否已构建。"""
        bm25 = get_bm25()
        return bm25 is not None and bm25.doc_count > 0

    @staticmethod
    def _rrf_fuse(
        vec_hits: list[SearchResult], kw_hits: list[SearchResult], k: int = 60
    ) -> list[SearchResult]:
        """RRF (Reciprocal Rank Fusion) 融合双路召回结果。"""
        rrf_scores: dict[str, float] = {}
        id_map: dict[str, SearchResult] = {}

        for rank, h in enumerate(vec_hits):
            rrf_scores[h.id] = rrf_scores.get(h.id, 0) + 1.0 / (k + rank + 1)
            id_map[h.id] = h

        for rank, h in enumerate(kw_hits):
            rrf_scores[h.id] = rrf_scores.get(h.id, 0) + 1.0 / (k + rank + 1)
            if h.id not in id_map:
                id_map[h.id] = h

        fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        for doc_id, rrf_score in fused:
            h = id_map[doc_id]
            result.append(SearchResult(
                id=h.id, text=h.text, score=round(rrf_score, 4),
                metadata={**h.metadata, "rrf_score": round(rrf_score, 4)},
            ))
        return result

    async def retrieve_with_context(
        self,
        query: str,
        *,
        knowledge_base_id: int | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> dict:
        hits = await self.retrieve(
            query=query, knowledge_base_id=knowledge_base_id,
            top_k=top_k, use_rerank=use_rerank,
        )
        context = build_context(hits) if hits else ""
        return {"hits": hits, "context": context}

    @traced("retrieval.build_context_for_exam")
    async def build_context_for_exam(
        self,
        knowledge_base_id: int,
        *,
        max_chunks: int = 10,
    ) -> str:
        # 多角度并行召回
        queries = ["关键概念 定义 原理", "方法 步骤 流程", "应用 案例 示例"]
        results = await asyncio.gather(*[
            recall(query=q, embedder=self._embedder, vector_store=self._vector_store,
                   top_k=5, knowledge_base_id=knowledge_base_id)
            for q in queries
        ])
        all_hits = [h for hits in results for h in hits]

        unique = deduplicate_by_text(all_hits)
        unique.sort(key=lambda x: x.score, reverse=True)
        return build_context(unique[:max_chunks], reorder=False)

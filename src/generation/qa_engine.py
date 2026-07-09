"""问答引擎 — 基于检索结果生成答案。

架构原则 #4: 所有检索操作通过 IRetrievalService 接口调用。

变更 (Phase 2 P1-5): 新增可选 ContextPipeline 参数，支持可插拔上下文增强步骤链。
"""
import json
import logging
from typing import AsyncGenerator, TYPE_CHECKING

from src.shared.config import settings
from src.interfaces.llm import ILLMClient, Message
from src.interfaces.vector_store import SearchResult
from src.interfaces.retrieval_service import IRetrievalService
from src.generation.prompts.qa import QA_SYSTEM_PROMPT

if TYPE_CHECKING:
    from src.generation.context.pipeline import ContextPipeline

logger = logging.getLogger(__name__)


def _hits_to_chunks(hits: list[SearchResult]) -> list[dict]:
    """SearchResult → chunk dict（管线输入格式）。"""
    return [
        {"text": h.text, "score": h.score, "metadata": h.metadata or {}}
        for h in hits
    ]


def _chunks_to_context(chunks: list[dict], max_chunks: int | None = None) -> str:
    if max_chunks is None:
        max_chunks = settings.retrieval.max_chunks
    """chunk dict 列表 → 格式化上下文字符串。"""
    if not chunks:
        return ""
    parts = []
    for i, c in enumerate(chunks[:max_chunks]):
        source = c.get("metadata", {}).get("source_file", "?")
        parts.append(f"【片段{i + 1}】(来源: {source})\n{c['text']}")
    return "\n\n---\n\n".join(parts)


async def qa_non_stream(
    question: str,
    llm_client: ILLMClient,
    retrieval_svc: IRetrievalService,
    knowledge_base_id: int | None = None,
    top_k: int = 5,
    use_rerank: bool = True,
    history: list[dict] | None = None,
    pipeline: "ContextPipeline | None" = None,
    guardrails: "GuardrailChain | None" = None,
) -> dict:
    """非流式 RAG 问答。"""
    # Opt-7: Input guard — 检查 prompt injection
    if guardrails:
        gr = await guardrails.check_input(question)
        if gr.action == "block":
            return {"question": question, "answer": gr.reason, "sources": []}

    if pipeline is not None:
        hits = await retrieval_svc.retrieve(
            query=question, knowledge_base_id=knowledge_base_id,
            top_k=top_k, use_rerank=use_rerank,
        )
        if not hits:
            return {"question": question, "answer": "当前知识库中暂无相关内容，建议上传相关资料后再提问。", "sources": []}

        chunks = _hits_to_chunks(hits)

        # Opt-7: Refuse guard — 低置信度拒答
        if guardrails:
            gr = await guardrails.check_input("", {"chunks": chunks})
            if gr.action == "block":
                return {"question": question, "answer": gr.reason, "sources": []}

        enhanced = await pipeline.process(chunks, question)
        context = _chunks_to_context(enhanced)
        sources = _build_sources_from_chunks(enhanced)
    else:
        result = await retrieval_svc.retrieve_with_context(
            query=question, knowledge_base_id=knowledge_base_id,
            top_k=top_k, use_rerank=use_rerank,
        )
        hits, context = result["hits"], result["context"]
        if not hits:
            return {"question": question, "answer": "当前知识库中暂无相关内容，建议上传相关资料后再提问。", "sources": []}
        sources = _build_sources(hits)

    messages = _build_messages(context=context, question=question, history=history)
    answer = await llm_client.chat(messages=messages, temperature=0.3)

    # Opt-7: Output guard — 引用验证 + 幻觉检测
    if guardrails:
        gr = await guardrails.check_output(answer, {"chunks": sources, "query": question})
        if gr.action == "block":
            return {"question": question, "answer": gr.reason, "sources": sources}

    return {"question": question, "answer": answer, "sources": sources}


async def qa_stream(
    question: str,
    llm_client: ILLMClient,
    retrieval_svc: IRetrievalService,
    knowledge_base_id: int | None = None,
    top_k: int = 5,
    use_rerank: bool = True,
    history: list[dict] | None = None,
    pipeline: "ContextPipeline | None" = None,
    guardrails: "GuardrailChain | None" = None,
) -> AsyncGenerator[str, None]:
    """流式 RAG 问答 — 返回 SSE 事件流。"""
    # Opt-7: Input guard
    if guardrails:
        gr = await guardrails.check_input(question)
        if gr.action == "block":
            yield f"data: {gr.reason}\n\n"
            yield "data: [DONE]\n\n"
            return

    if pipeline is not None:
        hits = await retrieval_svc.retrieve(
            query=question, knowledge_base_id=knowledge_base_id,
            top_k=top_k, use_rerank=use_rerank,
        )
        if not hits:
            yield "data: 当前知识库中暂无相关内容，建议上传相关资料后再提问。\n\n"
            yield "data: [DONE]\n\n"
            return

        chunks = _hits_to_chunks(hits)

        # Opt-7: Refuse guard
        if guardrails:
            gr = await guardrails.check_input("", {"chunks": chunks})
            if gr.action == "block":
                yield f"data: {gr.reason}\n\n"
                yield "data: [DONE]\n\n"
                return

        enhanced = await pipeline.process(chunks, question)
        context = _chunks_to_context(enhanced)
        sources = _build_sources_from_chunks(enhanced)
    else:
        result = await retrieval_svc.retrieve_with_context(
            query=question, knowledge_base_id=knowledge_base_id,
            top_k=top_k, use_rerank=use_rerank,
        )
        hits, context = result["hits"], result["context"]
        if not hits:
            yield "data: 当前知识库中暂无相关内容，建议上传相关资料后再提问。\n\n"
            yield "data: [DONE]\n\n"
            return
        sources = _build_sources(hits)

    messages = _build_messages(context=context, question=question, history=history)

    async for token in llm_client.chat_stream(messages=messages, temperature=0.3):
        yield f"data: {token}\n\n"

    yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def _build_messages(
    context: str,
    question: str,
    history: list[dict] | None,
) -> list[Message]:
    """构建 LLM 消息列表，含系统提示、历史对话、当前问题。"""
    messages: list[Message] = [Message(role="system", content=QA_SYSTEM_PROMPT)]

    if history:
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                messages.append(Message(role=role, content=content))

    prompt = f"## 知识库内容\n{context}\n\n## 用户问题\n{question}"
    messages.append(Message(role="user", content=prompt))
    return messages


def _build_sources(hits: list[SearchResult]) -> list[dict]:
    """构建来源引用列表。"""
    return [
        {
            "doc_id": h.metadata.get("doc_id", "?"),
            "chunk_index": h.metadata.get("chunk_index", 0),
            "score": round(h.score, 2),
            "text_preview": h.text[:200],
        }
        for h in hits
    ]


def _build_sources_from_chunks(chunks: list[dict]) -> list[dict]:
    """从 chunk dict 构建来源引用列表。"""
    return [
        {
            "doc_id": c.get("metadata", {}).get("doc_id", "?"),
            "chunk_index": c.get("metadata", {}).get("chunk_index", 0),
            "score": round(c.get("score", 0), 2),
            "text_preview": c.get("text", "")[:200],
        }
        for c in chunks
    ]

"""Mock LLM 服务（P2-C9）。

压测时替代 DeepSeek API，返回固定响应，避免 API 成本和速率限制。
兼容 OpenAI API 格式（/v1/chat/completions + /v1/embeddings）。

启动：
    python tests/load/mock_llm_server.py

配置 app 指向 mock：
    LLM__BASE_URL=http://localhost:8090/v1
    EMBEDDING__API_BASE_URL=http://localhost:8090/v1
"""
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="mock-llm", description="压测用 Mock LLM，兼容 OpenAI API")

EMBEDDING_DIM = 1024  # bge-m3 维度


@app.post("/v1/chat/completions")
async def chat_completions(req: dict):
    """Mock chat completions — 返回固定文本。"""
    return JSONResponse({
        "id": f"mock-chat-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.get("model", "mock"),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": "这是一条 mock 响应，用于压测验证链路。"},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    })


@app.post("/v1/embeddings")
async def embeddings(req: dict):
    """Mock embeddings — 返回固定维度向量。

    注：实际压测检索层（L2）时，embedding 质量影响检索结果，
    但对压测"链路通断 + 吞吐"无影响。如需真实检索效果，用 Ollama bge-m3。
    """
    text = req.get("input", "")
    n = len(text) if isinstance(text, list) else 1
    return JSONResponse({
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": [0.01] * EMBEDDING_DIM}
            for i in range(max(n, 1))
        ],
        "model": req.get("model", "mock"),
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    })


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8090)

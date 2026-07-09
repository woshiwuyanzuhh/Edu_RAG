# edu_rag v2.0 — 多阶段构建
# 注意: 以下依赖列表需与 pyproject.toml 的 [project].dependencies 保持同步
# 变更 pyproject.toml 后请同步更新此文件

FROM python:3.10-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache \
    fastapi uvicorn pydantic pydantic-settings python-multipart \
    jinja2 orjson aiofiles \
    sqlalchemy aiomysql pymysql \
    redis openai \
    chromadb sentence-transformers \
    PyMuPDF python-docx markdown \
    python-dotenv

# ── 运行阶段 ──
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（PyMuPDF 需要 libgl）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY . .

RUN mkdir -p data data/chroma

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "src.orchestration.app:app", "--host", "0.0.0.0", "--port", "8000"]

# edu_rag v2.0 — 多阶段构建
# 依赖来源: requirements.txt（由 pip-compile pyproject.toml 生成，锁定版本）
# 变更依赖: 编辑 pyproject.toml → pip-compile → requirements.txt 自动更新

FROM python:3.12-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY requirements.txt pyproject.toml ./
# 先装 CPU 版 torch（避免 2GB+ nvidia CUDA 包，Docker 内不需要 GPU）
RUN uv pip install --system --no-cache torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
# 再装主依赖（torch 已满足，跳过），然后用 --no-deps 装 arq（redis 版本冲突）
RUN uv pip install --system --no-cache -r requirements.txt && \
    uv pip install --system --no-cache --no-deps "arq>=0.26.0" && \
    uv pip install --system --no-cache "locust>=2.20.0"

# ── 运行阶段 ──
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（PyMuPDF 需要 libgl）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

RUN mkdir -p data

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

# P0-C4: 多 worker 利用多核（生产建议 CPU*2+1；可通过 docker-compose command 覆盖）
CMD ["uvicorn", "src.orchestration.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

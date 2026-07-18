# edu_rag v2.0 — 多阶段构建
# 依赖来源: requirements.txt（由 pip-compile pyproject.toml 生成，锁定版本）
# 变更依赖: 编辑 pyproject.toml → pip-compile → requirements.txt 自动更新

FROM python:3.10-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY requirements.txt pyproject.toml ./
# arq 在 pyproject.toml 中声明但被 pip-compile 遗漏，额外补充
RUN uv pip install --system --no-cache -r requirements.txt "arq>=0.26.0"

# ── 运行阶段 ──
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（PyMuPDF 需要 libgl）
# Trixie 已废弃 libgl1-mesa-glx，改用 libgl1；换清华源加速
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

RUN mkdir -p data data/chroma

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

# P0-C4: 多 worker 利用多核（生产建议 CPU*2+1；可通过 docker-compose command 覆盖）
CMD ["uvicorn", "src.orchestration.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# CLAUDE.md — edu_rag v2.0

> 本文件是 AI 助手的上下文文件，只记录**当前状态**。
> 变更历史见 [CHANGELOG.md](CHANGELOG.md)。

## 项目概述

四层 RAG 智能题库系统。113 源文件 · 14 接口契约 · 226 测试 · 架构评分 4.8/5。

```
ingress/ → retrieval/ → generation/ → orchestration/
     ↑       providers/ (LLM, Embedding)
interfaces/ ← 14 ABC 契约
shared/     ← Config / MySQL / Redis / Cache / Exceptions / Storage
observability/ ← Tracer / RAGAS / Prometheus Metrics
```

**关键设计**: 所有跨层通信仅通过接口。Generation 不直接 import Retrieval 内部模块。
指标定义放在 `observability/metrics.py`（不依赖 orchestration），避免分层违规。

## 快速启动

```bash
cd C:\Users\lenovo\Desktop\ml_dl_nlp\edu_rag
python src/orchestration/app.py    # 后端 → http://localhost:8000
cd frontend && npm run dev         # 前端 → http://localhost:5173
```

依赖: MySQL (edu_rag库) + Redis + Ollama (bge-m3 embedding + qwen3:4b LLM)

## 压力测试

```bash
# 1. 预灌入测试数据
python scripts/seed_test_data.py --reset

# 2. 启动 Mock LLM
python tests/load/mock_llm_server.py

# 3. 运行 Locust
locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time 5m --host http://localhost:8000
```

压测状态: 核心任务已完成（8/9），仅剩云环境 Docker Compose（需云服务器）。

## 关键配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `APP__REQUEST_TIMEOUT` | 30 | 全局请求超时秒数（SSE 豁免） |
| `APP__RATE_LIMIT_ENABLED` | true | 限流中间件开关 |
| `LLM__MAX_CONCURRENCY` | 10 | LLM 并发请求上限 |
| `EMBEDDING__MAX_CONCURRENCY` | 20 | Embedding 并发请求上限 |

## 关键文件

| 文件 | 用途 |
|------|------|
| `src/orchestration/app.py` | FastAPI 入口 |
| `src/orchestration/middleware/timeout.py` | 超时中间件（SSE 豁免） |
| `src/observability/metrics.py` | Prometheus 指标定义 |
| `src/providers/llm/client.py` | LLM 客户端（AsyncOpenAI + Semaphore） |
| `tests/load/locustfile.py` | Locust 压测脚本 |
| `scripts/seed_test_data.py` | 压测数据预灌入 |
| `docs/code-review-2026-07-18.md` | 最新项目 Review |

## 记忆文件

路径: `C:\Users\lenovo\.claude\projects\C--Users-lenovo-Desktop-ml-dl-nlp-edu-rag\memory\`

| 文件 | 内容 |
|------|------|
| `MEMORY.md` | 索引（自动加载） |
| `project-status.md` | 项目当前状态 |
| `architecture-reference.md` | 架构快速参考 |
| `git-workflow.md` | Git 工作流（HTTPS + 凭据） |

## 常用命令

```bash
make run          # 启动后端
make test         # 全部测试
make lint         # Ruff + MyPY
make docker       # Docker 全栈启动
```

## 恢复上下文

- "回顾系统状态" → 读 project-status.md + git status
- "开始压测" → 启动 mock LLM + seed_test_data.py + locust
- "架构 review" → 读 docs/code-review-2026-07-18.md + CHANGELOG.md

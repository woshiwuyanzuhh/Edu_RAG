# edu_rag v2.0 — 智能题库系统

基于四层 RAG（检索增强生成）架构的教育智能题库系统。支持多格式文档上传、知识库管理、智能出题、自动批改、多轮对话问答。

**架构评分: 4.8/5 | 113 源文件 | 14 接口契约 | 226 测试 | 压测就绪**

## ✨ 功能特性

- 📚 **多格式文档解析**：PDF、Word、Markdown、TXT，自动清洗 + 语义分块
- 🔍 **两阶段语义检索**：粗排召回（向量 + BM25 混合 RRF 融合）→ LLM 精排重排 + 分数融合
- 📐 **Lost-in-Middle 重排**：首尾强化，解决 LLM 长上下文注意力稀释
- 🤖 **智能出题**：选择题 / 简答题 / 判断题，多角度并行检索（概念 / 方法 / 应用）
- ✍️ **自动批改**：四维度评分（概念理解 25 / 分析能力 25 / 记忆准确 25 / 应用能力 25）
- 💬 **多轮对话问答**：会话持久化 (Redis + MySQL)，支持非流式 + SSE 流式双通道
- 🛡️ **Guardrails 安全链**：输入检测 / 低置信度拒答 / 幻觉检测 + 引用验证
- 🎯 **多知识库管理**：创建、编辑、删除（级联），分页查询
- 📊 **全链路可观测**：Tracer span + RAGAS 评估 + Prometheus 指标 + 检索日志
- ⚡ **多级缓存**：L1 进程内存 (60s) + L2 Redis (600s)，Redis 不可用时自动降级
- 🔒 **生产级弹性**：全局超时中间件 + LLM/Embedding 并发限流 + 滑动窗口限流 + 指数退避重试

## 🏗️ 架构

四层物理分层，14 个接口契约（ABC），严格面向接口编程。所有跨层通信仅通过接口，零分层违规。

```
src/
├── ingress/          # 文档写入: parse → clean → chunk → filter → embed
├── retrieval/        # 检索管线: recall → (hybrid RRF) → rerank → filters
├── generation/       # 生成引擎: qa / exam / context_pipeline / guardrails / hyde
├── orchestration/    # 编排中心: FastAPI + SSE + middleware + session + jobs + worker
├── providers/        # 基础设施: LLM 客户端 (AsyncOpenAI + Semaphore 限流)
├── interfaces/       # 14 个抽象接口 (架构基石)
├── shared/           # config / DB(MySQL+Redis) / cache / security / exceptions / storage
└── observability/    # Tracer + RAGAS + Prometheus Metrics + RetrievalLogger
```

> 详细架构分析见 [`docs/架构设计与完整链路分析.md`](docs/架构设计与完整链路分析.md)

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- MySQL 8.0+
- Redis 6.0+（可选，降级运行）
- Ollama（Embedding + LLM）或 OpenAI 兼容 API

### 2. 安装依赖

```bash
pip install -e ".[dev]"
```

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env 填入 API Key 和数据库连接
```

数据库表通过 Alembic 迁移自动创建（首次启动自动执行 `alembic upgrade head`）。

### 4. 启动

```bash
make run
# 或: python src/orchestration/app.py
# 或: uvicorn src.orchestration.app:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 前端（Vue 3 SPA）

```bash
cd frontend
npm install
npm run dev    # → http://localhost:5173
```

### 6. 访问

| 页面 | 地址 |
|------|------|
| 前端 SPA | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| Prometheus 指标 | http://localhost:8000/metrics |

## 🐳 Docker 部署

```bash
make docker
# 或: docker compose -f docker/docker-compose.yml up -d
```

支持 MySQL 主从 + Redis 哨兵 + Milvus 集群 + ARQ Worker + Prometheus + Grafana，详见 [`docker/`](docker/) 目录。

## 📦 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.115+ (async) + Vue 3 SPA (Ant Design Vue + Pinia) |
| 向量数据库 | ChromaDB (HNSW) / Milvus — 配置切换 |
| 关系数据库 | MySQL 8.0 + SQLAlchemy 2.0 async + aiomysql |
| 缓存 | Redis 7 (asyncio) — L1 进程 + L2 分布式 |
| LLM | OpenAI 兼容 (DeepSeek / OpenAI / Ollama qwen3:4b)，AsyncOpenAI 原生异步 |
| Embedding | Ollama bge-m3 (1024d) / sentence-transformers |
| 文档解析 | PyMuPDF / python-docx / markdown |
| 流式 | SSE (Server-Sent Events) via StreamingResponse |
| 异步任务 | ARQ (Redis 任务队列) |
| 可观测 | Prometheus 指标 + 自研 Tracer + RAGAS 评估 |
| 数据库迁移 | Alembic |

## 📁 项目结构

```
edu_rag/
├── src/
│   ├── interfaces/             # 14 个 ABC 抽象接口
│   ├── ingress/                # 文档写入管线 (parsers/cleaners/chunkers)
│   ├── retrieval/              # 检索管线 (recall/rerank/filters/keyword/embedder/vector_store)
│   ├── generation/             # 生成引擎 (qa/exam/guardrails/context/hyde/prompts)
│   ├── orchestration/          # 编排层 (app/api/middleware/session/jobs/worker)
│   ├── providers/              # 基础设施 (LLM 客户端 + 重试韧性)
│   ├── shared/                 # 共享层 (config/db/cache/security/exceptions/storage/models)
│   └── observability/          # 可观测性 (Tracer/RAGAS/Metrics/Logger)
├── frontend/                   # Vue 3 + Vite + Ant Design Vue + Pinia
├── tests/                      # 226 tests
│   ├── unit/                   # 单元测试
│   ├── integration/            # API 集成测试
│   ├── quality/                # RAGAS 质量评估
│   └── load/                   # Locust 压力测试
├── alembic/                    # 数据库迁移
├── docker/                     # Docker 部署 (Compose + 中间件配置)
├── scripts/                    # 工具脚本 (压测灌数/数据迁移/容灾检查/离线评估)
├── docs/                       # 项目文档
├── .env.example                # 环境变量模板
└── pyproject.toml
```

## 🔧 API 一览

| 模块 | 端点 | 方法 |
|------|------|------|
| knowledge | `/api/knowledge` | POST, GET |
| knowledge | `/api/knowledge/{id}` | GET, PUT, DELETE |
| documents | `/api/documents/upload` | POST |
| documents | `/api/documents` | GET |
| documents | `/api/documents/{id}` | DELETE |
| qa | `/api/qa` | POST (非流式) |
| qa | `/api/qa/stream` | POST (SSE 流式) |
| qa | `/api/qa/feedback` | POST, GET |
| exam | `/api/exam/generate` | POST |
| exam | `/api/exam/generate/stream` | POST (SSE 流式) |
| exam | `/api/exam/grade` | POST |
| exam | `/api/exam/records` | GET |

## ⚡ 压力测试

```bash
# 1. 预灌入测试数据
python scripts/seed_test_data.py --reset

# 2. 启动 Mock LLM（避免消耗 API 配额）
python tests/load/mock_llm_server.py

# 3. 运行 Locust 压测
locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time 5m --host http://localhost:8000
```

压测场景：QA 非流式 / QA SSE 流式 / 出题 / 文档列表 / 知识库列表。
监控：Prometheus 业务指标（请求计数 + 检索/LLM 延迟直方图）。

## 📊 测试

```bash
make test          # 全部测试
pytest tests/unit/ -v       # 单元测试
pytest tests/integration/   # 集成测试
pytest tests/quality/ -v    # RAGAS 质量评估
```

## 🎯 设计模式

| 模式 | 应用 |
|------|------|
| 依赖注入 | `RetrievalService(embedder, vector_store, llm_client)` |
| 策略 + 注册表 | `PARSER_REGISTRY`, `CLEANER_REGISTRY` |
| 门面 | `RetrievalService`, `GenerationService`, `IngestionService` |
| 模板方法 | `run_ingestion()` 管线 |
| 工厂 + 单例 | `get_embedder()`, `get_vector_store()` |
| ContextVar | `_request_id` 跨层传播 |
| Semaphore 限流 | LLM/Embedding 全局并发控制 |

## 📖 参考文档

- [ARCHITECTURE.md](ARCHITECTURE.md) — 完整架构文档
- [docs/架构设计与完整链路分析.md](docs/架构设计与完整链路分析.md) — 深度剖析
- [docs/系统架构设计准则.md](docs/系统架构设计准则.md) — 8 条架构原则
- [docs/code-review-2026-07-18.md](docs/code-review-2026-07-18.md) — 最新项目 Review
- [docs/启动与使用文档.md](docs/启动与使用文档.md) — 部署和使用说明
- [docs/disaster-recovery.md](docs/disaster-recovery.md) — 容灾方案
- [CLAUDE.md](CLAUDE.md) — AI 助手上下文

## 📄 License

MIT

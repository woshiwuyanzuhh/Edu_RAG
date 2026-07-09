# edu_rag v2.0 — 智能题库系统

基于四层 RAG（检索增强生成）架构的教育智能题库系统。支持多格式文档上传、知识库管理、智能出题、自动批改、多轮对话问答。

**架构评分: 4.8/5 | 226 tests | 全功能: 18/18 通过**

## ✨ 功能特性

- 📚 **多格式文档解析**：PDF、Word、Markdown、TXT，自动清洗 + 语义分块
- 🔍 **两阶段语义检索**：粗排召回（向量 + BM25 混合 RRF 融合）→ LLM 精排重排 + 分数融合
- 📐 **Lost-in-Middle 重排**：首尾强化，解决 LLM 长上下文注意力稀释
- 🤖 **智能出题**：选择题 / 简答题 / 判断题，多角度并行检索（概念 / 方法 / 应用）
- ✍️ **自动批改**：四维度评分（概念理解 25 / 分析能力 25 / 记忆准确 25 / 应用能力 25）
- 💬 **多轮对话问答**：会话持久化 (Redis + MySQL)，支持非流式 + SSE 流式双通道
- 🛡️ **Guardrails 安全链**：输入检测 / 低置信度拒答 / 幻觉检测 + 引用验证
- 🎯 **多知识库管理**：创建、编辑、删除（级联），分页查询
- 📊 **全链路追踪**：Tracer span + RAGAS 评估 + 用户反馈 + 检索日志
- ⚡ **多级缓存**：L1 进程内存 (60s) + L2 Redis (600s)，Redis 不可用时自动降级

## 🏗️ 架构

四层物理分层，12 个接口契约（ABC），严格面向接口编程。任何组件（Embedding / LLM / VectorStore / Parser）可独立替换。

```
src/
├── ingress/          # 文档写入: parse → clean → chunk → filter → embed
├── retrieval/        # 检索管线: recall → (hybrid RRF) → rerank → filters
├── generation/       # 生成引擎: qa / exam / context_pipeline / guardrails
├── orchestration/    # 编排中心: FastAPI + SSE + middleware + session
├── interfaces/       # 12 个抽象接口 (架构基石)
├── shared/           # config / DB(MySQL+Redis) / cache / security / exceptions
└── observability/    # Tracer + RAGAS + RetrievalLogger
```

> 详细架构分析见 [`架构设计与完整链路分析.md`](架构设计与完整链路分析.md)

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

# 初始化 MySQL 表
python scripts/init_db.py
```

### 4. 启动

```bash
make run
# 或: uvicorn src.orchestration.app:app --host 0.0.0.0 --port 8000 --reload
# 或: python src/orchestration/app.py
```

### 5. 访问

| 页面 | 地址 |
|------|------|
| 首页 | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 知识库 | http://localhost:8000/knowledge |
| 智能问答 | http://localhost:8000/qa |
| 智能出题 | http://localhost:8000/exam |
| 健康检查 | http://localhost:8000/health |
| Prometheus | http://localhost:8000/metrics |

## 🐳 Docker 部署

```bash
make docker
# 或: docker compose -f docker/docker-compose.yml up -d
```

## 📦 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.115+ (async) + Vue 3 SPA (Ant Design) |
| 向量数据库 | ChromaDB (HNSW) / Milvus — 配置切换 |
| 关系数据库 | MySQL 8.0 + SQLAlchemy 2.0 async + aiomysql |
| 缓存 | Redis 7 (aioredis) — L1 进程 + L2 分布式 |
| LLM | OpenAI 兼容 (DeepSeek / OpenAI / Ollama qwen3:4b) |
| Embedding | Ollama bge-m3 (1024d) / sentence-transformers |
| 文档解析 | PyMuPDF / python-docx / markdown |
| 流式 | SSE (Server-Sent Events) via StreamingResponse |
| 可观测 | 自研 Tracer + RAGAS + structlog |

## 📁 项目结构

```
edu_rag/
├── src/
│   ├── interfaces/             # 12 个 ABC 抽象接口
│   ├── ingress/                # 文档写入管线
│   │   ├── parsers/            # PDF / DOCX / MD / TXT
│   │   ├── cleaners/           # Base / Education / Gaming
│   │   └── chunkers/           # RecursiveChunker (语义分隔)
│   ├── retrieval/              # 检索管线
│   │   ├── service.py          # RetrievalService (门面)
│   │   ├── recall.py           # 粗排召回 + 查询扩展
│   │   ├── rerank.py           # LLM 精排 + 分数融合
│   │   ├── filters.py          # 去重/过滤/Lost-in-Middle
│   │   ├── embedder/           # Ollama / 本地 ST
│   │   ├── vector_store/       # ChromaDB / Milvus
│   │   ├── keyword/            # BM25 关键词索引
│   │   └── query/              # LLM 查询扩展器
│   ├── generation/             # 生成引擎
│   │   ├── qa_engine.py        # 非流式 + 流式问答
│   │   ├── exam_engine.py      # 出题 + 四维度批改
│   │   ├── llm/                # OpenAI 兼容客户端 + 重试韧性
│   │   ├── prompts/            # QA / Exam / Grade Prompt
│   │   ├── context/            # ContextPipeline (可插拔增强)
│   │   └── guardrails/         # Input/Output/Refuse Guard
│   ├── orchestration/          # 编排层
│   │   ├── app.py              # FastAPI 入口 + 生命周期
│   │   ├── api/                # knowledge / documents / qa / exam
│   │   ├── middleware/         # auth / request_id / error / rate_limit
│   │   ├── services.py         # 服务工厂
│   │   └── session.py          # 多轮会话 (Redis + MySQL)
│   ├── shared/                 # 共享层
│   │   ├── config.py           # Pydantic Settings (嵌套配置)
│   │   ├── database/           # MySQL + Redis
│   │   ├── models/             # ORM + Schemas
│   │   ├── cache.py            # 多级缓存策略
│   │   ├── security.py         # 密钥校验 + 安全警告
│   │   └── exceptions.py       # 8 种异常 + HTTP 映射
│   └── observability/          # Tracer + RAGAS + RetrievalLogger
├── frontend/                   # Vue 3 + Vite + Ant Design
├── tests/                      # 226 tests, 19 files
│   ├── unit/                   # 单元测试
│   ├── integration/            # API 集成测试
│   └── quality/                # RAGAS 质量评估
├── docker/                     # Docker 部署
├── scripts/                    # 工具脚本
├── .env.example                # 环境变量模板
├── pyproject.toml
└── 架构设计与完整链路分析.md     # 深度架构文档
```

## 🔧 API 一览

| 模块 | 端点 | 方法 |
|------|------|------|
| knowledge | `/api/kb` | POST, GET |
| knowledge | `/api/kb/{id}` | GET, PUT, DELETE |
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

## 🎯 设计模式

| 模式 | 应用 |
|------|------|
| 依赖注入 | `RetrievalService(embedder, vector_store, llm_client)` |
| 策略 + 注册表 | `PARSER_REGISTRY`, `CLEANER_REGISTRY` |
| 门面 | `RetrievalService`, `GenerationService`, `IngestionService` |
| 模板方法 | `run_ingestion()` 管线 |
| 工厂 + 单例 | `get_embedder()`, `get_vector_store()` |
| ContextVar | `_request_id` 跨层传播 |

## 📊 测试

```bash
# 全部测试
pytest tests/ -v

# 质量评估
pytest tests/quality/ -v

# 全功能端到端
python test_all_features.py
```

## 📖 参考文档

- [ARCHITECTURE.md](ARCHITECTURE.md) — 完整架构文档
- [架构设计与完整链路分析.md](架构设计与完整链路分析.md) — 深度剖析
- [系统架构设计准则.md](系统架构设计准则.md) — 8 条架构原则

## 📄 License

MIT

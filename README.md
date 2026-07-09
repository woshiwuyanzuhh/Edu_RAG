# edu_rag - 智能题库系统

基于四层 RAG（检索增强生成）架构的智能教育题库系统，支持多格式文档上传、知识库管理、智能出题、自动批改和多轮对话问答。

## 功能特性

- 📚 **多格式文档解析**：支持 PDF、Word、Markdown、TXT
- 🔍 **语义检索**：两阶段检索（粗排召回 + LLM 精排重排），Lost-in-Middle 上下文重排
- 🤖 **智能出题**：根据知识库自动生成选择题、简答题、判断题
- ✍️ **自动批改**：AI 驱动的答案批改 + 四维度评分（概念/分析/记忆/应用）
- 💬 **多轮对话问答**：基于知识库的 RAG 问答，支持会话历史和流式输出
- 🎯 **多知识库管理**：支持创建和管理多个知识库

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + Vue 3 SPA |
| 向量数据库 | ChromaDB（默认）/ Milvus（可选） |
| 关系数据库 | MySQL + SQLAlchemy (async) |
| 缓存 | Redis |
| LLM | OpenAI 兼容 API（DeepSeek/OpenAI/Ollama） |
| Embedding | Ollama bge-m3 / 本地 sentence-transformers |
| 文档解析 | PyMuPDF, python-docx, markdown |

## 架构

四层 RAG 架构，面向接口编程：

```
src/
├── ingress/       # 文档写入管线：解析 → 清洗 → 分块 → 过滤
├── retrieval/     # 检索：Embedding → 向量召回 → LLM 重排
├── generation/    # 生成：LLM 调用 → 出题引擎 → 问答引擎
├── orchestration/ # 编排：FastAPI 路由 → 中间件 → 会话管理
├── interfaces/    # 9 个抽象接口（面向接口编程，实现可替换）
├── shared/        # 共享：配置、数据库、缓存、安全、异常
└── observability/ # 全链路追踪（Tracer + RequestID）
```

## 快速开始

### 1. 环境要求

- Python 3.10+
- MySQL 8.0+
- Redis 6.0+
- Ollama（Embedding，可选）

### 2. 安装依赖

```bash
pip install -e ".[dev]"
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际配置
```

### 4. 启动服务

```bash
make run
# 或: uvicorn src.orchestration.app:app --reload --host 0.0.0.0 --port 8000
```

### 5. 访问

- 首页：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 知识库管理：http://localhost:8000/knowledge
- 智能问答：http://localhost:8000/qa
- 智能出题：http://localhost:8000/exam

## Docker 部署

```bash
make docker
# 或: docker compose -f docker/docker-compose.yml up -d
```

## 项目结构

```
edu_rag/
├── src/
│   ├── orchestration/      # FastAPI 入口 + API 路由 + 中间件
│   │   ├── app.py          # 应用入口 + 生命周期
│   │   ├── api/            # documents / qa / exam / knowledge
│   │   ├── middleware/     # auth / request_id / error_handler
│   │   └── session.py      # 多轮对话会话管理
│   ├── generation/         # LLM 客户端 + 出题引擎 + 问答引擎
│   │   ├── llm/            # OpenAI 兼容客户端 + 重试韧性
│   │   └── prompts/        # Prompt 模板
│   ├── retrieval/          # 检索管线
│   │   ├── recall.py       # 粗排召回（含查询扩展）
│   │   ├── rerank.py       # LLM 精排 + 分数融合
│   │   ├── filters.py      # 去重/过滤/Lost-in-Middle
│   │   ├── service.py      # RetrievalService（统一检索入口）
│   │   ├── embedder/       # Ollama / 本地 ST
│   │   ├── vector_store/   # ChromaDB / Milvus
│   │   └── query/          # 查询扩展
│   ├── ingress/            # 文档写入管线
│   │   ├── parsers/        # PDF / DOCX / MD / TXT
│   │   ├── cleaners/       # 通用 / 教育 / 游戏
│   │   └── chunkers/       # 递归语义分块
│   ├── interfaces/         # 抽象接口（ABC）
│   ├── shared/             # 配置 / DB / 缓存 / 安全 / 异常
│   └── observability/      # 全链路追踪
├── frontend/               # Vue 3 SPA (Ant Design)
│   └── src/ (views/api/router/App.vue)
├── docker/                 # Docker 部署配置
├── tests/                  # 测试
└── data/                   # 上传文件目录
```

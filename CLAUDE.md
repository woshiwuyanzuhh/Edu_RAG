# CLAUDE.md — edu_rag v2.0

## 项目概述

四层 RAG 智能题库系统。103 源文件 · 14 接口契约 · 226 测试 · 架构评分 4.8/5。

```
ingress/ → retrieval/ → generation/ → orchestration/
     ↑       providers/ (LLM, Embedding)
interfaces/ ← 14 ABC 契约
shared/     ← Config / MySQL / Redis / Cache / Exceptions
```

**关键设计**: 所有跨层通信仅通过接口。Generation 不直接 import Retrieval 内部模块。

## 快速启动

```bash
cd C:\Users\lenovo\Desktop\ml_dl_nlp\edu_rag
python src/orchestration/app.py    # → http://localhost:8000
```

依赖: MySQL (edu_rag库) + Redis + Ollama (bge-m3 embedding + qwen3:4b LLM)

---

## 🔴 当前任务 — 压力测试方案

**状态**: 计划完成，待实施。9 个任务，预估 10.5h。

| # | 任务 | 阶段 | 状态 |
|---|------|------|:--:|
| 1 | 云环境 Docker Compose 配置 | Phase 0 | ⬜ pending |
| 2 | 数据库连接池扩容 | Phase 1 | ⬜ pending |
| 3 | LLM 并发控制 + Mock 模式 | Phase 1 | ⬜ pending |
| 4 | 请求超时中间件 | Phase 1 | ⬜ pending |
| 5 | 限流开关 + Embedding 并发控制 | Phase 1 | ⬜ pending |
| 6 | 自定义 Prometheus 指标 | Phase 2 | ⬜ (依赖 2-5) |
| 7 | Locust 压力测试场景 | Phase 3 | ⬜ pending |
| 8 | 测试数据准备 | Phase 4 | ⬜ (依赖 7) |
| 9 | 验证 & 文档 | Phase 5 | ⬜ (依赖全部) |

**核心决策**:
- 压测在**云服务器**上进行（本机配置太差）
- 框架: Locust（Python 原生，支持 SSE 流式）
- LLM: Mock 模式避免消耗 API 配额
- 监控: Prometheus + Grafana (docker-compose profile)

**关键文件**:
- 方案详情: `.claude/plans/snazzy-squishing-penguin.md`
- Memory: `[[stress-testing-plan]]`
- 需新建 12 个文件，修改 9 个文件

---

## 未提交的代码变更（git status）

10 个文件已修改但未提交：
- `providers/` 提取 — LLM 客户端从 generation/ 下沉到独立基础设施层
- `orchestration/jobs/` — API 层与业务逻辑解耦
- `BM25 知识库隔离` — 修复跨知识库搜索结果泄漏
- 向后兼容 re-exports (`__getattr__` 惰性加载)

---

## 记忆文件

路径: `C:\Users\lenovo\.claude\projects\C--Users-lenovo-Desktop-ml-dl-nlp-edu-rag\memory\`

| 文件 | 内容 |
|------|------|
| `MEMORY.md` | 索引（自动加载） |
| `project-status.md` | 项目当前状态 |
| `architecture-assessment.md` | 架构评估 |
| `architecture-reference.md` | 架构快速参考 |
| `stress-testing-plan.md` | 压力测试方案 |
| `git-workflow.md` | 每次改动必须 commit + push |

---

## 常用命令

```bash
make run          # 启动后端
make test         # 全部测试
make lint         # Ruff + MyPy
make docker       # Docker 全栈启动
```

## 恢复上下文

下次打开时说：
- "继续压力测试方案" → 读 plan 文件 + 任务列表
- "回顾系统状态" → 读 project-status.md + git status
- "开始实施 Phase X" → 读 plan + 执行对应任务

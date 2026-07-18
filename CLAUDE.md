# CLAUDE.md — edu_rag v2.0

## 项目概述

四层 RAG 智能题库系统。103 源文件 · 14 接口契约 · 226 测试 · 架构评分 4.8/5。

```
ingress/ → retrieval/ → generation/ → orchestration/
     ↑       providers/ (LLM, Embedding)
interfaces/ ← 14 ABC 契约
shared/     ← Config / MySQL / Redis / Cache / Exceptions
observability/ ← Tracer / RAGAS / Prometheus Metrics
```

**关键设计**: 所有跨层通信仅通过接口。Generation 不直接 import Retrieval 内部模块。
指标定义放在 `observability/metrics.py`（不依赖 orchestration），避免分层违规。

## 快速启动

```bash
cd C:\Users\lenovo\Desktop\ml_dl_nlp\edu_rag
python src/orchestration/app.py    # → http://localhost:8000
```

依赖: MySQL (edu_rag库) + Redis + Ollama (bge-m3 embedding + qwen3:4b LLM)

---

## ✅ 压力测试方案 — 实施进度

**状态**: 核心任务已完成，待云环境验证。

| # | 任务 | 阶段 | 状态 | 说明 |
|---|------|------|:--:|------|
| 1 | 云环境 Docker Compose 配置 | Phase 0 | ⬜ pending | 需云服务器 |
| 2 | 数据库连接池扩容 | Phase 1 | ✅ done | 已在 config 中配置 pool_size/max_overflow |
| 3 | LLM 并发控制 | Phase 1 | ✅ done | Semaphore 限流，LLM__MAX_CONCURRENCY |
| 4 | 请求超时中间件 | Phase 1 | ✅ done | TimeoutMiddleware，SSE 豁免，APP__REQUEST_TIMEOUT |
| 5 | 限流开关 + Embedding 并发控制 | Phase 1 | ✅ done | APP__RATE_LIMIT_ENABLED + EMBEDDING__MAX_CONCURRENCY |
| 6 | Prometheus 指标埋点 | Phase 2 | ✅ done | QA/Exam/Doc 计数 + 检索/LLM 延迟直方图 |
| 7 | Locust 压力测试场景 | Phase 3 | ✅ done | locustfile.py 已有（修正端点路径+加 stream/exam） |
| 8 | 测试数据准备 | Phase 4 | ✅ done | scripts/seed_test_data.py 预灌入脚本 |
| 9 | 验证 & 文档 | Phase 5 | ✅ done | CLAUDE.md 更新 + 依赖补全 |

**核心决策**:
- 压测在**云服务器**上进行（本机配置太差）
- 框架: Locust（Python 原生，支持 SSE 流式）
- LLM: Mock 模式避免消耗 API 配额
- 监控: Prometheus + Grafana (docker-compose profile)

**新增配置项**（通过环境变量覆盖）:
| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `APP__REQUEST_TIMEOUT` | 30 | 全局请求超时秒数（SSE 豁免） |
| `APP__RATE_LIMIT_ENABLED` | true | 限流中间件开关 |
| `LLM__MAX_CONCURRENCY` | 10 | LLM 并发请求上限 |
| `EMBEDDING__MAX_CONCURRENCY` | 20 | Embedding 并发请求上限 |

**关键文件**:
- 压测脚本: `tests/load/locustfile.py`
- Mock LLM: `tests/load/mock_llm_server.py`
- 数据灌入: `scripts/seed_test_data.py`
- 指标定义: `src/observability/metrics.py`
- 超时中间件: `src/orchestration/middleware/timeout.py`
- 方案详情: `.claude/plans/snazzy-squishing-penguin.md`

---

## 架构改进记录

### v2.0 架构优化（本轮完成）
- **providers/ 提取** — LLM 客户端从 generation/ 下沉到独立基础设施层
- **orchestration/jobs/** — API 层与业务逻辑解耦
- **BM25 知识库隔离** — 修复跨知识库搜索结果泄漏
- **HyDE 下沉** — 从 orchestration 移到 generation 层（修复分层违规）
- **指标定义下沉** — 从 orchestration/middleware 移到 observability（修复分层违规）
- **AsyncOpenAI 迁移** — LLM/Embedding 客户端从同步 SDK 迁移到原生异步
- **Redis scan()** — 废弃 keys()，新增非阻塞 scan()
- **并发控制** — LLM/Embedding 全局 Semaphore 限流
- **超时保护** — 全局请求超时中间件（SSE 豁免）
- **Alembic 迁移** — 手动创建初始迁移脚本

### 向后兼容 re-exports
- `orchestration/middleware/metrics.py` → `observability/metrics.py`
- `orchestration/query_preprocessor.py` → `generation/hyde.py`

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

# 压测
python scripts/seed_test_data.py --reset    # 预灌入测试数据
locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time 5m --host http://localhost:8000
```

## 恢复上下文

下次打开时说：
- "回顾系统状态" → 读 project-status.md + git status
- "开始压测" → 启动 mock LLM + seed_test_data.py + locust
- "架构 review" → 读 architecture-reference.md + 本文件架构改进记录

# CHANGELOG — edu_rag

> 本文件记录所有有意义的架构变更和功能迭代，按时间倒序排列。
> 当前项目状态见 [CLAUDE.md](CLAUDE.md)。

---

## 2026-07-18 (夜) — 工程化优化轮（Docker/QA流式/LLM缓存）

**范围**: 7 项工程化优化任务，已完成 4 项

### Docker 镜像修复
- **Dockerfile**: Python 3.10 → 3.12（与 requirements.txt 锁定的包版本对齐）
- **torch CPU 版**: `--index-url https://download.pytorch.org/whl/cpu`，镜像体积减少 2GB+
- **arq --no-deps**: arq 的 redis<6 约束与 redis==8 冲突，用 `--no-deps` 绕过
- **requirements.txt**: 移除 arq 行（移到 Dockerfile 单独安装）

### QA 流式输出优化
- **打字机光标**: CSS `blink-cursor` 动画，流式输出时显示闪烁竖线
- **停止按钮**: AbortController + fetch signal，用户可中断生成
- **点点动画**: 检索中/思考中显示波浪点动画
- **滚动节流**: requestAnimationFrame，避免每个 token 触发 scrollHeight 重排

### LLM 响应缓存
- **精确匹配缓存**: `GenerationService.qa()` 对无历史对话的单轮 QA 缓存
- **缓存 key**: question + kb_id + top_k + use_rerank 的 MD5 哈希
- **配置项**: `GENERATION__QA_CACHE_TTL`（默认 1800 秒，0=禁用）

### 压测报告更新
- 勾选已完成优化项（MySQL max_connections、限流配置化）

---

## 2026-07-18 (晚) — 压力测试执行 + 优化项落地

**范围**: L1/L2/L3 共 9 轮压测 + 3 项压测优化修复

### 压测结果
- **L1 接入层** (Mock LLM): 50/100/200 并发，最优并发 100，QPS 63，P99 < 1s
- **L2 检索层** (Mock LLM): 50/100/200 并发，Milvus+BM25 稳定，0% 系统失败
- **L3 全链路** (真实 DeepSeek): 5/10/20 并发，0% 失败，QA P50=1.6s，P99=3.2s
- **报告**: `docs/load-test-report-2026-07-18.md`

### 优化修复
- **MySQL max_connections** — docker-compose.yml 添加 `--max-connections=500`，200 并发 500 错误从 17.6% 降至 0%
- **限流配置可配置化** — rate_limit 阈值从硬编码改为环境变量
- **Dockerfile 依赖** — 加入 `locust>=2.20.0`，docker-compose.yml 添加 `build` 配置

### 新增配置项
| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `APP__RATE_LIMIT_DEFAULT` | 60 | 普通 API 限流（次/窗口） |
| `APP__RATE_LIMIT_LLM` | 20 | LLM 接口限流（次/窗口） |
| `APP__RATE_LIMIT_WINDOW` | 60 | 限流窗口大小（秒） |

### 变更文件
- `docker/docker-compose.yml` — MySQL max_connections + app build 配置
- `docker/Dockerfile` — 加入 locust 依赖
- `src/shared/config.py` — AppConfig 新增 3 个限流配置字段
- `src/orchestration/middleware/rate_limit.py` — 硬编码改为从配置读取
- `docs/load-test-report-2026-07-18.md` — 压测报告（新增）
- `tests/load/locustfile.py` — 端点路径修正 (/api/knowledge → /api/kb)

---

## 2026-07-18 — 压力测试方案实施

**范围**: Phase 1-5 压测任务（8/9 完成，仅剩云环境 Docker）

### 新增
- `src/orchestration/middleware/timeout.py` — 全局请求超时中间件（SSE 豁免）
- `src/observability/metrics.py` — Prometheus 业务指标定义（从 orchestration/middleware 下沉）
- `scripts/seed_test_data.py` — 压测数据一键预灌入脚本
- `docs/code-review-2026-07-18.md` — 项目 Review 报告（4.8/5）

### 变更
- **指标定义下沉** — 从 `orchestration/middleware/metrics.py` 移到 `observability/metrics.py`
  - 修复分层违规：providers/retrieval 可合法埋点
  - 原路径保留 re-export 向后兼容
- **LLM 并发控制** — `OpenAICompatClient` 全局 Semaphore（`LLM__MAX_CONCURRENCY`，默认 10）
- **Embedding 迁移 AsyncOpenAI** — `OllamaEmbedder` 从同步 SDK + to_thread 迁移到原生异步 + Semaphore
- **限流开关** — `RateLimitMiddleware` 增加 `APP__RATE_LIMIT_ENABLED` 开关
- **Prometheus 指标埋点** — QA/Exam/Doc 请求计数 + 检索/LLM 延迟直方图
- **locustfile.py** — 修正端点路径 + 新增 SSE/Exam 压测场景
- **依赖补全** — requirements.txt 补 arq/prometheus，pyproject.toml dev 加 locust

### 新增配置项
| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `APP__REQUEST_TIMEOUT` | 30 | 全局请求超时秒数（SSE 豁免） |
| `APP__RATE_LIMIT_ENABLED` | true | 限流中间件开关 |
| `LLM__MAX_CONCURRENCY` | 10 | LLM 并发请求上限 |
| `EMBEDDING__MAX_CONCURRENCY` | 20 | Embedding 并发请求上限 |

---

## 2026-07-16 — v2.0 架构重构

**范围**: providers 提取 + jobs 解耦 + BM25 隔离 + 前端重构 + 容灾配置

### 架构改进
- **providers/ 提取** — LLM 客户端从 generation/ 下沉到独立基础设施层
- **orchestration/jobs/** — API 层与业务逻辑解耦（`process_document_ingestion` / `delete_document_resources`）
- **BM25 知识库隔离** — 修复跨知识库搜索结果泄漏（`_bm25_indexes: dict[int | None, BM25Index]`）
- **HyDE 下沉** — 从 orchestration 移到 generation 层（修复分层违规），原路径 re-export
- **AsyncOpenAI 迁移** — LLM 客户端从同步 SDK 迁移到原生异步
- **Redis scan()** — 废弃 keys()（DeprecationWarning），新增非阻塞 scan()
- **Alembic 迁移** — 手动创建初始迁移脚本（0001_initial_schema.py，6 张表）
- **接口统一** — 全部 interfaces/ 从 Protocol 统一为 ABC + @abstractmethod

### 前端重构
- Design Token 系统（双主题变量 + 全局样式）
- 3 个通用组件（EmptyState / LoadingSkeleton / PageHeader）
- 2 个 Pinia stores（chat 多会话 + global 全局）
- 2 个 composables（useKnowledgeBases / useSSE）
- 5 个页面全面重写（Home / QA / Upload / Exam / Knowledge）

### 容灾配置
- MySQL 主从配置（master.cnf / slave.cnf）
- Redis 哨兵配置（sentinel.conf）
- docker-compose.cloud.yml（云环境 + Prometheus + Grafana）
- scripts/failover_check.py（故障切换检查）

### 向后兼容 re-exports
- `orchestration/middleware/metrics.py` → `observability/metrics.py`
- `orchestration/query_preprocessor.py` → `generation/hyde.py`
- `generation/llm/` → `providers/llm/`（`__getattr__` 惰性加载）

---

## 2026-07-09 — v1.0 初始版本

- 四层 RAG 架构搭建（ingress / retrieval / generation / orchestration）
- 14 个 ABC 接口契约
- 多格式文档解析（PDF / DOCX / MD / TXT）
- 两阶段语义检索（向量召回 + BM25 混合 + LLM 精排）
- QA 问答（非流式 + SSE 流式）+ 智能出题 + 四维度批改
- Guardrails 安全链（输入检测 / 拒答 / 幻觉检测）
- 多级缓存（L1 进程 + L2 Redis）
- 全链路 Tracer + RAGAS 评估
- 226 测试用例

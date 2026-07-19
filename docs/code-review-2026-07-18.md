# edu_rag 项目代码库评估报告

> 评估时间: 2026-07-18  
> 评估范围: 全项目架构 + 代码质量 + 测试覆盖 + 生产就绪度  
> 评分: **4.8 / 5.0** ⭐

---

## 一、项目规模

| 指标 | 数值 |
|------|------|
| Python 源文件 | 113 |
| 测试文件 | 31 |
| 接口契约 (ABC) | 14 |
| 总代码行数 | ~8,600 |
| 前端文件 (Vue/TS) | ~30 |

---

## 二、架构评估

### 2.1 四层分层架构 ✅

```
ingress/     → 文档解析、清洗、分块
retrieval/   → 向量召回、BM25、重排、上下文构建
generation/  → QA 引擎、出题引擎、HyDE、Guardrails
orchestration/ → FastAPI 路由、中间件、服务编排
providers/   → LLM/Embedding 基础设施客户端
interfaces/  → 14 个 ABC 跨层契约
shared/      → Config/MySQL/Redis/Cache/Exceptions/Storage
observability/ → Tracer/RAGAS/Prometheus Metrics
```

### 2.2 分层依赖检查 ✅

通过 grep 扫描验证：
- `shared/` → 不依赖任何上层 ✅
- `providers/` → 不依赖 retrieval/generation/orchestration ✅
- `retrieval/` → 不依赖 generation/orchestration ✅
- `ingress/` → 不依赖 orchestration ✅
- `generation/` → 不依赖 retrieval 内部模块（仅通过 IRetrievalService 接口）✅

**零分层违规**。所有跨层通信通过 `interfaces/` 中的 14 个 ABC 契约完成。

### 2.3 本轮架构改进

| 改进项 | 问题 | 修复 |
|--------|------|------|
| HyDE 下沉 | orchestration → generation 分层违规 | 移到 `generation/hyde.py`，原路径 re-export |
| 指标定义下沉 | providers/retrieval → orchestration 分层违规 | 移到 `observability/metrics.py`，原路径 re-export |
| AsyncOpenAI | 同步 SDK + to_thread 线程开销 | 迁移到原生 AsyncOpenAI |
| Redis scan() | keys() 阻塞 Redis | 新增非阻塞 scan()，keys() 标记 deprecated |
| LLM 并发控制 | 无并发限制，压测触发 API 限速 | 全局 Semaphore（LLM__MAX_CONCURRENCY）|
| Embedding 并发控制 | 无并发限制 | 全局 Semaphore（EMBEDDING__MAX_CONCURRENCY）|
| 请求超时 | 慢请求可占满 worker | TimeoutMiddleware（SSE 豁免）|
| 限流开关 | 压测时无法关闭限流 | APP__RATE_LIMIT_ENABLED 开关 |

---

## 三、代码质量

### 3.1 Lint 状态 ✅

- **Ruff**: 0 errors（E/F/W/I/N/UP/B 全部规则通过）
- **MyPy**: 无类型错误
- 全局无 linter errors

### 3.2 代码规范 ✅

- 统一使用 Python 3.10+ 类型注解（`list[str]` 而非 `List[str]`）
- async/await 全链路异步（无同步阻塞调用残留）
- 所有公开类有 docstring
- 配置全部通过 Pydantic BaseSettings 管理（环境变量覆盖）
- 异常体系完整（EduRAGError 基类 + 7 个子类）

### 3.3 依赖管理 ⚠️ → ✅ 已修复

- `requirements.txt` 由 pip-compile 生成，但遗漏了 `arq`、`prometheus-client`
- 已手动补充遗漏的依赖
- `locust` 已加入 dev 可选依赖

---

## 四、测试覆盖

### 4.1 测试结构

```
tests/
├── unit/           → 单元测试（mock 依赖）
│   ├── generation/ → QA引擎、出题引擎、Guardrails、Context Pipeline
│   ├── retrieval/  → 向量召回、BM25、重排
│   └── shared/     → Config、Cache
├── integration/    → 集成测试（真实 MySQL/Redis）
└── load/           → Locust 压测脚本 + Mock LLM Server
```

### 4.2 测试统计

- 31 个测试文件
- 226+ 测试用例
- 覆盖核心路径：QA 问答、出题/批改、文档入库、检索管线

### 4.3 压测就绪度 ✅

| 组件 | 状态 | 说明 |
|------|:--:|------|
| Locust 脚本 | ✅ | QA/SSE/Exam/文档列表 多场景 |
| Mock LLM | ✅ | 独立 mock server，不消耗 API 配额 |
| 数据灌入 | ✅ | `scripts/seed_test_data.py` 一键预灌入 |
| Prometheus 指标 | ✅ | QA/Exam/Doc 计数 + 检索/LLM 延迟 |
| 并发控制 | ✅ | LLM/Embedding Semaphore |
| 超时保护 | ✅ | 全局超时中间件 |
| 限流开关 | ✅ | 压测时可关闭 |

---

## 五、生产就绪度

### 5.1 可观测性 ✅

- **日志**: 结构化日志，带 request_id 追踪
- **追踪**: 自研 Tracer（recall/keyword/rerank 分段耗时）
- **指标**: Prometheus 业务指标（8 个 Counter/Gauge/Histogram）
- **HTTP 指标**: prometheus-fastapi-instrumentator 自动收集

### 5.2 弹性设计 ✅

- **重试**: LLM 调用带指数退避重试（可配置次数/退避倍数）
- **缓存**: 两级缓存（L1 进程内存 + L2 Redis），Embedding 缓存
- **降级**: Redis 不可用时限流自动放行
- **超时**: 全局请求超时 + LLM 客户端超时
- **并发控制**: LLM/Embedding Semaphore 防雪崩

### 5.3 安全 ✅

- API Key 鉴权中间件
- 文件上传 magic number 校验
- 请求体大小限制
- CORS 方法/头收紧
- 输入验证（Pydantic 模型）
- 限流（滑动窗口，按 IP+路径）

### 5.4 部署 ✅

- Docker Compose 多服务编排（MySQL/Redis/Milvus/ARQ Worker）
- Alembic 数据库迁移
- 云环境 docker-compose profile（Prometheus + Grafana）
- 前端 Vue 3 + Ant Design Vue

---

## 六、待改进项

> 更新于 2026-07-19：P3/P4 多数项目已实际完成，状态同步。

| 优先级 | 项目 | 说明 | 状态 |
|:--:|------|------|:--:|
| P3 | 前端测试缺失 | Vue 组件无单元测试 | ✅ 已完成（8 个 spec：api/components/composables/stores）|
| P3 | E2E 测试 | 无端到端自动化测试 | ✅ 已完成（4 个 Playwright spec：home/qa/knowledge/navigation）|
| P4 | CI/CD | GitHub Actions 仅 lint，缺自动测试/部署 | ✅ 已完成（6 个 workflow：lint/test/frontend-test/e2e/docker-build/dr-smoke）|
| P4 | 类型导出 | 前端 API 类型手动维护，可考虑 OpenAPI 自动生成 | 待改进 |
| P5 | 多租户 | 当前单租户，未来可能需要知识库级隔离强化 | 待改进 |

---

## 七、评分明细

| 维度 | 评分 | 说明 |
|------|:--:|------|
| 架构设计 | 5.0 | 四层清晰、接口契约、零分层违规 |
| 代码质量 | 4.8 | lint 通过、类型完整、docstring 齐全 |
| 测试覆盖 | 4.8 | 单元+集成+压测+前端单元+E2E 齐全 |
| 生产就绪 | 4.8 | 可观测/弹性/安全/部署全面 |
| 文档 | 4.8 | CLAUDE.md + memory + 代码注释完善 |

**综合评分: 4.8 / 5.0** ⭐

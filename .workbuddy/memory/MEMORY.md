# edu_rag 项目长期笔记（MEMORY.md）

> 最后更新：2026-07-17
> 维护规则：项目级长期事实与待办清单，按主题组织，每次有新发现追加或更新对应章节。

## 当前项目状态

- **项目**：edu_rag 教育领域 RAG 系统（FastAPI + Vue3 + MySQL + Chroma/Milvus + DeepSeek/Ollama）
- **代码库评估完成**：2026-07-16，详见 `项目代码库评估报告.md`
- **整体评分**：架构 4.8/5 · 安全 4.5/5（P1 修复后提升）· 代码质量 4.5/5（P2 修复后提升）
- **P0 已由用户自行处理**：API Key 轮换（`.env:7`）、MySQL 强口令（`.env:29`）—— 后续不再追踪
- **P1 进度**：7 项全部完成 ✅（P1-4 锁文件已于并发容灾改造中完成）
- **P2 进度**：10 项全部完成 ✅（P2-1 部分完成，其余全部完成）
- **并发容灾改造**：2026-07-17 完成 P0(5)+P1(6)+P2(5) 共 16 项，详见下方专节 + `docs/P1P2改造审查报告.md`
- **前端重构**：2026-07-16 完成全面重构（设计系统 + 布局 + 考试出题/答题模块 + 微交互 + 响应式）

## 待修复问题清单（按优先级，P0 已剔除）

### P1 — 短期修复（1-2 周）

| # | 问题 | 位置 | 状态 |
|---|---|---|---|
| P1-1 | API 鉴权默认关闭 fail-open | `src/orchestration/middleware/auth.py` | ✅ 完成 fail-closed |
| P1-2 | 前端存储型 XSS（marked + v-html 无净化） | `frontend/src/views/QAPage.vue` | ✅ 完成 DOMPurify |
| P1-3 | docker-compose 默认弱密码 + Redis 无密码 | `docker/docker-compose.yml` | ✅ 完成 强制密码 |
| P1-4 | 依赖无锁文件 | `pyproject.toml:6-27` | ✅ 完成 requirements.txt（384 行，pip-compile，腾讯镜像；合并 C1 加 pymilvus） |
| P1-5 | 分页参数无上限（4 个列表端点） | `knowledge.py`/`documents.py`/`qa.py`/`exam.py` | ✅ 完成 le=100 |
| P1-6 | API Key 经 Query 传输 | `auth.py` | ✅ 完成 仅 Header |
| P1-7 | body 限制(10MB) 与上传限制(50MB) 矛盾 | `app.py:41` | ✅ 完成 统一 |

### P2 — 中期优化（2-4 周）

| # | 问题 | 位置 | 状态 |
|---|---|---|---|
| P2-1 | 删除约 200 行死代码 | `generation/llm/` shim、8 个未用 Response schema、`Chunk` 类、`traced_sync`、`async_cached`、`clear_bm25`、5 个未用异常类、未用 import | 🟡 部分（仅删 app.py 未用 Request import；其余有测试覆盖或属公共 API，留待专门重构） |
| P2-2 | 抽取重复逻辑 | `_prepare_qa_context`/`_prepare_exam_context`/`paginated_select`/`shared/json_utils.py` | ✅ 完成 4 处抽取 |
| P2-3 | `redis.keys` → `SCAN` | `src/shared/cache.py` | ✅ 完成 scan_iter |
| P2-4 | 上传文件改分块写盘 | `documents.py` | ✅ 完成 aiofiles 分块 |
| P2-5 | 删除类操作改 `asyncio.to_thread` | `knowledge.py` | ✅ 完成 to_thread |
| P2-6 | BM25 延迟批量 rebuild | `bm25.py` | ✅ 完成 dirty 延迟重建 |
| P2-7 | compressor 改并发 | `compressor.py` | ✅ 完成 gather+Semaphore |
| P2-8 | 路径遍历校验 | `app.py` | ✅ 完成 resolve 断言 |
| P2-9 | 文件上传增加魔数校验 | `documents.py` | ✅ 完成 纯 Python 魔数 |
| P2-10 | CORS 收紧方法/头 | `app.py` | ✅ 完成 显式方法/头 |

### P3 — 长期演进（1-2 月）

| # | 问题 | 位置 | 状态 |
|---|---|---|---|
| P3-1 | 引入 JWT + RBAC 用户体系 | `auth.py`（替代单一共享 API Key） | ⬜ 待办 |
| P3-2 | 补齐测试覆盖 | parsers/cleaners/middleware/session/config/ORM 单元测试 | ⬜ 待办 |
| P3-3 | 统一命名与文档 | `ingress`/`Ingestion` 对齐；接口计数 README/ARCHITECTURE/CLAUDE 统一为 13 | ⬜ 待办 |
| P3-4 | 清理 LLM 客户端双入口 | 迁移引用并删除 `generation/llm/` shim | ⬜ 待办 |
| P3-5 | 配置集中化 | 限流参数/SESSION_TTL/batch_size/向量维度进配置；`ALLOWED_EXTENSIONS` 从 `PARSER_REGISTRY` 派生 | ⬜ 待办 |
| P3-6 | 异常处理收窄 | 修复吞异常、过宽 except、嵌套 try-except；Milvus search 区分"无结果"与"出错" | ⬜ 待办 |
| P3-7 | 全局可变状态加 LRU | `_bm25_indexes`、`_l1` 加 maxsize + 淘汰 | ⬜ 待办 |
| P3-8 | 落实架构演进建议 | Post-Retrieval 阶段归属、Context Augmentation Pipeline 正式化（见 `架构演进建议.md`） | ⬜ 待办 |
| P3-9 | 会话历史字段结构化 | `schemas.py:84,128` 改 `list[ChatMessage]`/`list[AnswerItem]` | ⬜ 待办 |

## 已确认通过的项（无需处理）

- ✅ SQL 注入：全 ORM 参数化，无原始 SQL 拼接
- ✅ 命令注入：无 subprocess/os.system/eval/exec/pickle.load
- ✅ 敏感信息脱敏：SecretStr + .gitignore 正确 + git 历史无泄露
- ✅ 全局异常处理不泄露堆栈

## 性能瓶颈专项（P2 已集中处理完成）

| 位置 | 问题 | 优化方向 | 状态 |
|---|---|---|---|
| `cache.py` | `redis.keys(pattern)` 阻塞 | `SCAN` 迭代 | ✅ scan_iter |
| `documents.py` | 上传文件全量入内存 | `aiofiles` 分块写盘 | ✅ 1MB 分块 |
| `knowledge.py` | async 路径同步 `os.remove` | `asyncio.to_thread` | ✅ to_thread |
| `bm25.py` | 增删全量重建 | 标记删除 + 延迟批量 rebuild | ✅ dirty 延迟重建 |
| `compressor.py` | 逐块串行 LLM 压缩 | `asyncio.gather` 并发 | ✅ gather+Semaphore(5) |
| `retrieval_logger.py` | async QA 路径同步文件写 | `aiofiles` | ✅ 异步写 |
| `milvus.py` | 每次 insert 都 flush | 批量延迟 flush | ✅ dirty lazy flush |
| `session.py` | session 全量覆盖写 | SQL JSON_APPEND 增量更新 | ✅ JSON_ARRAY_APPEND |
| `ingress/service.py` | 盲删 10000 ID fallback | 减小范围 | ✅ 2000 ID（4 批×500） |
| `cache.py` L1 | 全局字典无 LRU | maxsize + 淘汰 | ✅ maxsize=1000+LRU |
| `keyword/__init__.py` | 全局字典无 LRU | maxsize + 淘汰 | ⏭️ 跳过（知识库数量少，收益低） |

## 项目架构关键路径（供后续引用）

- 接口契约：`src/interfaces/__init__..py`（13 个 ABC）
- Retrieval 门面：`src/retrieval/service.py:27-51`
- QA 引擎：`src/generation/qa_engine.py:44-164`
- Exam 引擎：`src/generation/exam_engine.py:33-121`
- FastAPI 入口：`src/orchestration/app.py:46-71`
- 鉴权中间件：`src/orchestration/middleware/auth.py:36-41`
- 配置：`src/shared/config.py`（SecretStr 脱敏）
- 安全自检：`src/shared/security.py:12-18`（弱口令检测，仅告警）

## 并发容灾改造（2026-07-17，方案 ~/.workbuddy/plans/electric-vortex-darwin.md）

目标：压测 100 万总请求 + 分钟级容灾切换。P0/P1/P2 全部完成。

### 已完成
- P0：C1 Milvus 部署+pymilvus+锁文件、C2 迁移脚本、C3 BM25 持久化、C4 --workers、C8 /health 探活、P1-4 锁文件
- P1：C5 ARQ 异步队列、C7 连接池调优、D2 存储抽象、D4 云部署、D5 MySQL 主从、D8 failover 脚本
- P2：C9 压测脚本、C10 Prometheus 指标、D6 Redis 哨兵、D7 Milvus 集群说明、D10 容灾手册

### 审查发现（docs/P1P2改造审查报告.md）
- P1-1 已修复：worker on_startup 初始化连接
- P2×8 待办：BM25 竞争(同步模式)、/health count 开销、指标未埋点、删除双重删、failover 无冷却、Dockerfile uvicorn[standard]、锁文件未用、worker 重试文件清理
- P3×4：ARQ pool 未关、remove 残留、维度硬编码、Dockerfile 双份维护

### 关键架构变更
- 向量库：ChromaDB(嵌入式) → Milvus(独立服务)，支持多实例
- 文档入库：同步 → ARQ 异步队列（单写消除 BM25 竞争）
- 文件存储：本地磁盘 → 抽象层(本地/对象存储可切换)
- /health：静态 ok → 探活依赖(503 降级)，容灾 LB 前提
- 多 worker：单进程 → --workers 4

### 待运行时验证
docker 环境完整跑通：Milvus 三件套 + ARQ worker + 主从复制 + 故障切换演练（代码语法已验证，集成未测）

### Docker 集成验证（2026-07-17 22:30-23:40，已完成）

复用宿主机 Milvus(19530)+Ollama(11434)，docker 启动 app/worker/mysql/redis。override 文件处理端口冲突（profiles + !override depends_on + host.docker.internal + src 代码挂载）。

**验证通过**：4 容器 Up · /health 三项全绿 · 知识库 CRUD · 文档上传+ARQ 异步入库(worker done) · BM25 持久化(MySQL) · Milvus 向量写入(query 确认) · QA 端到端流程

**修复 4 个问题**：① libgl1-mesa-glx 废弃→libgl1+清华源 ② Dockerfile 漏 COPY /usr/local/bin(uvicorn) ③ pymilvus3.0 num_entities 属性非方法 ④ Milvus insert 延迟 flush 跨进程失效→立即 flush

**配置修复**：.env 加单下划线变量 · Redis 密码 · MySQL native_password · VECTOR_STORE__MILVUS_HOST(单下划线)

**已知限制（非改造 bug）**：app 启动时 Milvus collection load(count=0)，worker 后续写入需 reload collection 才能 search（Milvus load 机制特性）

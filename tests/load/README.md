# 压测说明（P2-C9）

> **状态**: ✅ L1/L2/L3 共 9 轮压测已完成（2026-07-18），0% 系统失败率
> **完整报告**: `docs/load-test-report-2026-07-18.md`
> **关键结论**: Mock 最优并发 100（QPS 63），真实 LLM 20 并发 QA P99=3.2s

## 分层压测策略

| 层级 | 压什么 | LLM | 100 万请求成本 | 工具 |
|---|---|---|---|---|
| L1 接入层 | 鉴权/路由/限流/CORS | mock | ¥0 | locustfile.py + mock LLM |
| L2 检索层 | Milvus+BM25+MySQL+Redis | mock | ¥0 | locustfile.py + mock LLM |
| L3 全链路 | 端到端含 LLM | 真实 | 采样 3 万 ≈ ¥180 | locustfile.py + DeepSeek |
| L4 LLM 探配额 | DeepSeek API 速率上限 | 真实 | 几千次 ≈ ¥50 | 独立脚本 |

**总成本预估：¥100-500**（非全量真实 LLM 的 ¥6000）。

## 前置准备

### 1. 启动 Mock LLM 服务（L1/L2 用）

```bash
python tests/load/mock_llm_server.py  # 监听 :8090
```

### 2. 配置 app 指向 mock（L1/L2）

`.env` 或环境变量：
```
LLM__BASE_URL=http://localhost:8090/v1
EMBEDDING__API_BASE_URL=http://localhost:8090/v1
```

### 3. 启动被测服务

```bash
docker compose -f docker/docker-compose.yml up -d
```

### 4. 安装 Locust

```bash
pip install locust
```

## 执行压测

### L1/L2 — 接入层/检索层（mock LLM，100 万请求）

```bash
# 1000 并发，每秒新增 50，跑 10 分钟
locust -f tests/load/locustfile.py --headless -u 1000 -r 50 --run-time 10m \
    --host http://localhost:8000

# 100 万总请求目标：调高 -u（如 3000）和 --run-time
# 观察 QPS、P50/P99 延迟、失败率
```

### L3 — 全链路（真实 LLM，采样）

```bash
# 还原 .env 指向 DeepSeek，低并发采样
locust -f tests/load/locustfile.py --headless -u 50 -r 5 --run-time 5m \
    --host http://localhost:8000
```

### L4 — LLM 配额探测

单独脚本压 DeepSeek API 上限（本目录未含，按需编写）。

## 关键指标

- **QPS**：每秒请求数（目标 L1/L2 ≥ 2000）
- **P99 延迟**：99 分位响应时间（目标 < 2s，L3 受 LLM 限制可放宽）
- **失败率**：非 2xx 响应占比（目标 < 1%）
- **瓶颈定位**：通过 Prometheus /metrics + Grafana 观察 DB/Redis/Milvus 各环节延迟

## 瓶颈排查

1. QPS 上不去 → 查 uvicorn worker 数、MySQL 连接池、限流配置
2. P99 高 → 查 Prometheus 链路，定位是检索/DB/LLM 哪一段
3. 失败率高 → 查 /health 依赖状态、连接池耗尽、超时

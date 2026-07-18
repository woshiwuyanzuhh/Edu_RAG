# 容灾切换手册（P2-D10）

## 架构概览

```
[DNS / 云 LB] ──┬── 本地机房（主）
                │   ├─ app ×4 (uvicorn workers) + ARQ worker
                │   ├─ MySQL 主
                │   ├─ Redis 主
                │   ├─ Milvus standalone
                │   └─ 文件存储（本地 / 对象存储）
                │
                └── 云上备机（热备）
                    ├─ app ×4 + ARQ worker（预热就绪）
                    ├─ MySQL 从（主从复制，只读）
                    ├─ Redis 独立（或哨兵故障转移）
                    ├─ Milvus standalone
                    └─ 文件存储
```

**RTO 目标**：分钟级（1-5min，探活 15s + 切换）
**RPO 目标**：秒级（MySQL 半同步复制）

## 故障检测

`scripts/failover_check.py` 每 5s 探活本地 `/health`（P0-C8 含 MySQL+Redis+向量库探活）：
- 连续 3 次失败（15s）→ 触发切换
- 发送告警 webhook + 调用 DNS/LB API 切换流量

部署：
```bash
# cron 每 5s 执行（单次检查模式）
* * * * * python scripts/failover_check.py --once --local-url http://localhost:8000 \
    --webhook-url https://hooks.example.com/alert --dns-api https://dns.api/switch

# 或常驻循环
nohup python scripts/failover_check.py --local-url http://localhost:8000 --interval 5 &
```

## 切换流程（自动，分钟级）

1. `failover_check` 探活失败 3 次 → 标记本地不可用
2. 云 LB 健康检查剔除本地 → 流量全切云上备机
3. 备机承接流量（预热就绪：BM25 从 MySQL 加载、模型加载、Milvus 连接）
4. MySQL 从库承接读请求；写请求处理：
   - **方案 A（推荐，读多写少场景）**：从库提升为主
     ```sql
     STOP REPLICA; SET GLOBAL read_only=0; RESET REPLICA ALL;
     ```
   - **方案 B**：暂拒写请求，等本地恢复（教育查询场景可接受）

## 回切流程（手动，灰度）

1. 本地恢复，确认服务正常（`/health` 返回 200）
2. MySQL 主从校验数据一致性（`pt-table-checksum` 或人工抽检）
3. 灰度回切（DNS/LB 权重调整）：
   - 10% 流量回本地 → 观察 10min
   - 50% → 观察 10min
   - 100%
4. 全程 Prometheus 监控 + 人工确认
5. 回切后重新建立主从复制（云上作为本地从）

## 演练步骤（建议月度）

1. 启动云上备机：`docker compose -f docker/docker-compose.cloud.yml up -d`
2. 确认 MySQL 主从复制正常：从库执行 `SHOW REPLICA STATUS\G`（Slave_IO/SQL_Running=Yes）
3. 模拟本地故障：`docker compose -f docker/docker-compose.yml stop app`
4. 观察 failover_check 触发切换（15s 内）
5. 验证云上备机承接流量：
   - `curl http://<cloud-host>:8100/health` → 200
   - `curl -X POST http://<cloud-host>:8100/api/qa/ask -d '{...}'` → 正常响应
6. 模拟恢复：`docker compose -f docker/docker-compose.yml start app`
7. 灰度回切 10% → 50% → 100%
8. 记录演练耗时，优化 RTO

## 数据同步策略

| 数据 | 同步方式 | RPO | 依赖 |
|---|---|---|---|
| MySQL（会话/考试/文档/BM25 缓存） | 主从复制（半同步） | 秒级 | D5 master/slave.cnf |
| Redis | 哨兵故障转移 / 主从复制 | 秒级（AOF） | D6 sentinel.conf |
| Milvus | 独立集群，切换后迁移脚本同步增量 | 分钟级 | C2 迁移脚本 |
| BM25 索引 | 持久化到 MySQL，随主从复制 | 秒级 | P0-C3 |
| 上传文件 | 对象存储共享 / rsync | 秒-分钟级 | P1-D2 |
| 会话/考试/反馈 | 已在 MySQL，随主从复制 | 秒级 | v2.0 已外部化 |

## 注意事项

- **写一致性**：切换瞬间可能有未复制的写丢失（半同步下 RPO≈秒级）。教育场景以读为主，影响小。
- **Milvus 增量**：切换后本地新写入的向量需手动跑 `migrate_chroma_to_milvus.py` 同步到云（幂等清空重建，适合停机窗口）。
- **BM25 一致性**：P0-C3 已持久化到 MySQL，随主从复制同步，备机启动 `load_all_bm25_from_db` 自动加载。
- **文件存储**：对象存储（D2）模式下双机共享同一 bucket；本地存储需 rsync/inotify 实时同步。
- **多 worker BM25 竞争**：P1-C5 异步队列后，文档入库集中在 ARQ worker 单进程，消除多 app worker 写竞争。
- **演练**：务必月度演练，避免切换时发现配置漂移（凭证/端口/防火墙）。

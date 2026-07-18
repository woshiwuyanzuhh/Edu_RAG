# 容灾切换手册（已部署 — 4GB 阿里云版）

> **最后更新**：2026-07-19
> **部署状态**：✅ 已上线运行
> **云服务器**：`116.62.121.27`（阿里云轻量 2C4G，杭州，Ubuntu 22.04）
> **本地服务器**：成都联通家庭宽带（动态公网 IP）

---

## 实际部署架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        用户浏览器                                  │
│                   http://116.62.121.27                            │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP :80
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              云服务器（杭州 阿里云 2C4G）                           │
│                                                                    │
│  ┌───────────┐    ┌──────────────────────────────────────────┐   │
│  │  Nginx    │───▶│  upstream edu_rag_backend                │   │
│  │  :80      │    │    primary: edu_rag_frps:18000 (frp)     │   │
│  └───────────┘    │    backup:  docker-app-1:8000 (云上备机)  │   │
│                   └──────────────────────────────────────────┘   │
│                                                                    │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │  frps     │  │  App     │  │  MySQL   │  │  Redis       │    │
│  │  :7000    │  │  :8100   │  │  从库    │  │  备库        │    │
│  │  :7500    │  │  2 workers│  │  :3308  │  │  :6381      │    │
│  │  3个代理   │  │  512M    │  │  512M   │  │  192M        │    │
│  └─────┬─────┘  └──────────┘  └────┬─────┘  └──────────────┘    │
│        │                         实时复制                        │
│        │ frp 隧道                     ▲                          │
│  ┌─────┴─────────────────────────────┼──────────────┐           │
│  │  18000 → 本地 App:8000             │              │           │
│  │  13306 → 本地 MySQL:3307           │              │           │
│  │  11434 → 本地 Ollama:11434         │              │           │
│  └────────────────────────────────────┼──────────────┘           │
│        │                              │                          │
│  ┌─────┴─────┐  ┌──────────────┐  ┌──┴──────────┐               │
│  │  etcd     │  │  minio       │  │  Milvus     │               │
│  │  256M     │  │  256M        │  │  1280M      │               │
│  └───────────┘  └──────────────┘  └─────────────┘               │
│                                                                    │
│  内存: 1.3GB / 3.4GB (+ 4GB swap)                                 │
│  定时: 每分钟故障检测 + 每天凌晨3点备份                            │
└──────────────────────────────────────────────────────────────────┘
         │ frp 隧道                    │ MySQL 主从复制
         ▼                             ▼
┌──────────────────────────────────────────────────────────────────┐
│              本地服务器（成都联通家庭宽带）                         │
│                                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐     │
│  │  App     │  │  MySQL   │  │  Redis   │  │  Milvus      │     │
│  │  :8000   │  │  主库    │  │  主库    │  │  主库        │     │
│  │  4 workers│  │  :3307  │  │  :6380  │  │  :19530     │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘     │
│                                                                    │
│  ┌──────────┐  ┌──────────┐                                       │
│  │  frpc    │  │  Ollama  │  ← bge-m3 模型                       │
│  │  客户端   │  │  :11434  │                                       │
│  └──────────┘  └──────────┘                                       │
│                                                                    │
│  公网 IP: 101.204.208.80（动态，重启路由器可能变化）               │
└──────────────────────────────────────────────────────────────────┘
```

**RTO 实测**：~20秒（Nginx max_fails=3, fail_timeout=15s）
**RPO**：秒级（MySQL 异步复制，主从延迟 <1s）

---

## 4GB 内存优化说明

由于云服务器只有 4GB 内存，采用以下优化策略：

| 优化项 | 节省内存 | 说明 |
|--------|---------|------|
| 不启动 Ollama | 3-4 GB | Embedding 通过 frp 连本地 Ollama |
| 不启动 Redis 从+Sentinel | 0.3 GB | 简化为单 Redis |
| 不启动 ARQ Worker | 0.4 GB | 热备只承接查询 |
| App workers 2→4 | 0.4 GB | 降低并发处理能力 |
| MySQL buffer_pool 256M | 0.5 GB | 限制内存使用 |
| 配置 4GB swap | - | 防 OOM 兜底 |

完整版（升级到 8GB+ 内存后）：
```bash
docker compose -f docker/docker-compose.cloud.yml --env-file .env.cloud up -d
```

---

## 关键配置

### frp 内网穿透

由于本地是家庭宽带（封入站端口），使用 frp 内网穿透：

| 隧道 | 云上端口 | 本地端口 | 用途 |
|------|---------|---------|------|
| `local-app` | `frps:18000` | `localhost:8000` | Nginx 转发流量到本地 App |
| `local-mysql` | `frps:13306` | `localhost:3307` | 云上从库主从复制 |
| `local-ollama` | `frps:11434` | `localhost:11434` | 云上 App 调用本地 Embedding |

- **frp 仪表盘**：`http://116.62.121.27:7500`（admin / `<FRP_DASHBOARD_PASSWORD>`）
- **认证 token**：`<见 .env.cloud FRP_TOKEN>`
- **配置文件**：`docker/frp/frps.toml`（云上）、`docker/frp/frpc.toml`（本地）

### MySQL 主从复制

```
本地主库 (binlog.000006:157) → frp隧道 → 云上从库 (edu_rag_frps:13306)
```

- 认证方式：`mysql_native_password`（非默认的 caching_sha2_password）
- 复制方式：传统 binlog 位置复制（非 GTID）
- 从库只读：`read_only=ON`

---

## 容灾组件清单

| 组件 | 文件 | 部署位置 | 状态 |
|------|------|---------|------|
| **Nginx 入口** | `docker/nginx/nginx.conf` | 云服务器 | ✅ 运行中 |
| **frp 服务端** | `docker/frp/frps.toml` | 云服务器 | ✅ 运行中 |
| **frp 客户端** | `docker/frp/frpc.toml` | 本地 | ✅ 运行中 |
| **App（云上）** | `docker/docker-compose.cloud.4gb.yml` | 云服务器 | ✅ 运行中 |
| **MySQL 从库** | `docker/mysql/slave.cnf` | 云服务器 | ✅ 复制中 |
| **数据备份** | `scripts/backup.py` | 云服务器 | ✅ cron 每天3点 |
| **故障检测** | `scripts/failover_check.py` | 云服务器 | ✅ cron 每分钟 |
| **MySQL 提升** | `scripts/mysql_promote.py` | 云服务器 | ✅ 就绪 |
| **Milvus 同步** | `scripts/sync_milvus.py` | 云服务器 | ✅ 就绪 |
| **容灾演练** | `scripts/disaster_drill.py` | 云服务器 | ✅ 就绪 |
| **swap 配置** | `scripts/setup_swap.sh` | 云服务器 | ✅ 4GB swap |
| **健康检查** | `/health/live`, `/health/ready` | 双端 | ✅ 正常 |

---

## 故障检测与切换

### 自动切换流程（已验证 ✅）

```
本地 App 故障
    │
    ├── Nginx 被动健康检查
    │   ├── 第1次请求失败（max_fails=1/3）
    │   ├── 第2次请求失败（max_fails=2/3）
    │   └── 第3次请求失败（max_fails=3/3）
    │       → 标记 primary 为 down（fail_timeout=15s）
    │
    ├── Nginx 自动切到 backup（docker-app-1:8000）
    │   → 用户请求由云上备机承接
    │
    └── 总耗时：~20秒（RTO）
```

**实测验证**（2026-07-19）：
- 停止本地 App → Nginx 20秒内自动切换到云上备机 ✅
- 恢复本地 App → Nginx 自动切回本地主 ✅

### 手动操作

```bash
# SSH 登录云服务器
ssh root@116.62.121.27

# 查看当前状态
docker ps
curl http://localhost:80/health/ready

# 查看 frp 隧道状态
curl -s -u admin:<FRP_DASHBOARD_PASSWORD> http://localhost:7500/api/proxy/tcp

# 查看 MySQL 主从状态
docker exec docker-mysql_cloud-1 mysql -u root -p"$MYSQL_PASSWORD" -e "SHOW REPLICA STATUS\G"

# 手动提升 MySQL 从库为主库（故障切换后需要写能力时）
python3 /opt/edu_rag/scripts/mysql_promote.py

# 同步 Milvus 数据
python3 /opt/edu_rag/scripts/sync_milvus.py
```

---

## 回切流程（故障恢复后）

当本地服务恢复后：

1. **启动本地服务**：
   ```bash
   # 本地执行
   docker start docker-app-1
   ```

2. **等待 Nginx 自动恢复**：
   - Nginx 会在 `fail_timeout`（15s）后重新探测 primary
   - 探测成功后自动将流量切回本地

3. **验证回切**：
   ```bash
   curl http://116.62.121.27/health/live
   # timestamp 应为本地 App 的启动时间
   ```

4. **重建 MySQL 主从**（如从库被提升为主库）：
   ```bash
   # 在云上执行
   python3 /opt/edu_rag/scripts/mysql_replication_setup.py
   ```

---

## 日常运维

### 检查日志

```bash
# SSH 登录云服务器
ssh root@116.62.121.27

# 故障检测日志
tail -f /var/log/edu_rag_failover.log

# 备份日志
tail -f /var/log/edu_rag_backup.log

# Nginx 日志
docker logs -f edu_rag_nginx

# App 日志
docker logs -f docker-app-1

# frp 日志
docker logs -f edu_rag_frps   # 云上
docker logs -f edu_rag_frpc   # 本地
```

### 本地公网 IP 变化时

家庭宽带 IP 可能变化，更新方式：

```bash
# 1. 查询新 IP（本地执行）
curl ifconfig.me

# 2. 更新 .env.cloud（云上执行）
ssh root@116.62.121.27
vi /opt/edu_rag/.env.cloud
# 修改 LOCAL_PUBLIC_IP 和 NGINX_LOCAL_HOST

# 3. frpc 配置不需要改（frpc 连的是云服务器 IP，不受本地 IP 变化影响）
```

### 月度演练

```bash
ssh root@116.62.121.27
cd /opt/edu_rag
python3 scripts/disaster_drill.py
```

---

## 阿里云安全组（防火墙规则）

以下端口已在阿里云控制台放行（来源 `0.0.0.0/0`）：

| 端口 | 用途 | 必须 |
|------|------|------|
| 80 | Nginx HTTP（统一入口） | ✅ |
| 7000 | frp 服务端 | ✅ |
| 7500 | frp 仪表盘 | ✅ |
| 22 | SSH | ✅（默认已开） |

---

## 注意事项

- **本地公网 IP 动态**：家庭宽带 IP 可能变化，但 frpc 连接的是云服务器固定 IP，不受影响
- **frp 隧道依赖**：本地 frpc 必须保持运行，否则云上无法访问本地的 App/MySQL/Ollama
- **Embedding 依赖本地**：云上 App 的 Embedding 通过 frp 调用本地 Ollama，本地故障时 Embedding 不可用（但查询不受影响）
- **MySQL 异步复制**：非半同步，极端情况下可能有秒级数据丢失
- **swap 性能**：4GB swap 是兜底方案，频繁使用 swap 会影响性能
- **演练频率**：建议每月演练一次，确保切换正常

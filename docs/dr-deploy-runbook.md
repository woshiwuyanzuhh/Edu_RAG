# edu_rag 容灾部署运行手册（4GB 阿里云版）

> **部署状态**: ✅ 已上线（2026-07-19）
> 云服务器: `116.62.121.27`（杭州，2C4G，50GB，Ubuntu 22.04）
> 本地公网IP: `101.204.208.80`（成都联通，动态）
> 容灾方案: 本地主 + 云备机，frp 内网穿透
> **统一入口**: `http://116.62.121.27`
> **frp 仪表盘**: `http://116.62.121.27:7500`（admin / `<FRP_DASHBOARD_PASSWORD>`）

---

## 架构总览

```
┌─────────────────────────────┐         ┌──────────────────────────────┐
│         本地（主）           │         │        云服务器（备）          │
│                             │         │                              │
│  ┌─────────┐  ┌──────────┐  │         │  ┌──────────┐  ┌─────────┐  │
│  │  App    │  │  MySQL   │  │         │  │  Nginx   │→ │  App    │  │
│  │ (主流量) │  │  (主库)  │  │         │  │ (入口)   │  │ (备机)  │  │
│  └────┬────┘  └────┬─────┘  │         │  └──────────┘  └────┬────┘  │
│       │            │        │         │                      │       │
│  ┌────┴────┐  ┌────┴─────┐  │         │  ┌──────────┐  ┌────┴────┐  │
│  │ Ollama  │  │  Redis   │  │         │  │ MySQL    │  │  Redis  │  │
│  │(Embed)  │  │  (主)    │  │         │  │ (从库)   │  │ (备)    │  │
│  └────┬────┘  └──────────┘  │         │  └────┬─────┘  └─────────┘  │
│       │                    │         │       │                      │
│  ┌────┴────┐               │         │  ┌────┴─────┐  ┌─────────┐  │
│  │ frpc    │═══════════════┼─────────┼→│ frps     │  │ Milvus  │  │
│  │ (客户端) │  frp 隧道      │         │  │ (服务端) │  │ (备)    │  │
│  └─────────┘               │         │  └──────────┘  └─────────┘  │
└─────────────────────────────┘         └──────────────────────────────┘
```

**frp 隧道映射**：
- 云上 `frps:13306` → 本地 MySQL(3307)  [主从复制]
- 云上 `frps:11434` → 本地 Ollama(11434) [Embedding]

---

## 部署步骤

### Part A: 本地操作（在你的电脑上）

#### A1. 配置 frp 客户端

```bash
cd C:\Users\lenovo\Desktop\ml_dl_nlp\edu_rag

# 生成 frp token 并配置两端文件
bash scripts/setup_frp.sh
```

执行后会自动生成 token，并更新：
- `docker/frp/frps.toml`（服务端配置）
- `docker/frp/frpc.toml`（客户端配置）

#### A2. 启动本地 frp 客户端

```bash
# 启动 frp 客户端（保持运行）
docker compose -f docker/docker-compose.frpc.yml up -d

# 查看日志确认连接成功
docker logs -f edu_rag_frpc
```

看到 `login to server success` 表示连接成功。

#### A3. 确认本地 MySQL 和 Ollama 端口

```bash
# 确认本地 MySQL 映射端口（docker-compose.yml 中应为 3307:3306）
docker ps --format "table {{.Names}}\t{{.Ports}}" | findstr mysql

# 确认 Ollama 运行在 11434
curl http://localhost:11434/api/tags
```

> 如果本地 MySQL 端口不是 3307，需要修改 `docker/frp/frpc.toml` 中的 `localPort`。

---

### Part B: 云服务器操作（SSH 登录后）

#### B1. SSH 登录

```bash
ssh root@116.62.121.27
```

#### B2. 上传项目代码

**方式1: 从本地 SCP 上传**（在本地 PowerShell 执行）

```powershell
scp -r C:\Users\lenovo\Desktop\ml_dl_nlp\edu_rag root@116.62.121.27:/opt/edu_rag
```

**方式2: 从 GitHub 克隆**（如果有仓库）

```bash
cd /opt
git clone https://github.com/your-repo/edu_rag.git
cd edu_rag
```

#### B3. 系统初始化

```bash
cd /opt/edu_rag

# 执行初始化脚本（安装 Docker、Python、Nginx 等）
bash scripts/cloud_init.sh

# 配置 4GB swap（防止 OOM）
bash scripts/setup_swap.sh
```

#### B4. 配置环境变量

```bash
cp docker/.env.cloud.example .env.cloud
vi .env.cloud
```

需要修改的值：

```bash
# MySQL 密码（与本地一致！主从复制需要相同密码）
MYSQL_PASSWORD=你的本地MySQL密码

# Redis 密码
REDIS_PASSWORD=你的Redis密码

# DeepSeek API Key
OPENAI_API_KEY=sk-你的deepseek密钥

# 本地公网 IP
LOCAL_PUBLIC_IP=101.204.208.80
NGINX_LOCAL_HOST=101.204.208.80

# frp 配置（已由 setup_frp.sh 生成，这里填相同的 token）
# 实际 token 在 docker/frp/frps.toml 中已设置
```

#### B5. 同步 frp 配置

如果用 SCP 上传了代码，`docker/frp/frps.toml` 已经在本地配好了 token。
确认 token 一致：

```bash
# 查看 frps.toml 中的 token
grep "auth.token" docker/frp/frps.toml

# 应该与本地 frpc.toml 中的 token 一致
# grep "auth.token" docker/frp/frpc.toml
```

#### B6. 启动云上服务（4GB 优化版）

```bash
cd /opt/edu_rag

# 构建镜像
docker compose -f docker/docker-compose.cloud.yml \
  -f docker/docker-compose.cloud.4gb.yml \
  --env-file .env.cloud build

# 启动所有服务
docker compose -f docker/docker-compose.cloud.yml \
  -f docker/docker-compose.cloud.4gb.yml \
  --env-file .env.cloud up -d

# 查看状态
docker compose -f docker/docker-compose.cloud.yml \
  -f docker/docker-compose.cloud.4gb.yml ps
```

#### B7. 验证 frp 隧道

```bash
# 访问 frp 仪表盘
curl http://localhost:7500 -u admin

# 或浏览器访问 http://116.62.121.27:7500
# 看到 local-mysql 和 local-ollama 两个代理在线 = 成功
```

#### B8. 配置 MySQL 主从复制

```bash
# 进入云上 MySQL 容器
docker exec -it edu_rag_mysql_cloud mysql -u root -p

# 在 MySQL 中执行：
# （替换密码为实际密码）
CHANGE MASTER TO
  MASTER_HOST='frps',
  MASTER_PORT=13306,
  MASTER_USER='root',
  MASTER_PASSWORD='你的本地MySQL密码',
  MASTER_AUTO_POSITION=1;

START REPLICA;

# 查看复制状态
SHOW REPLICA STATUS\G
```

看到 `Replica_IO_Running: Yes` 和 `Replica_SQL_Running: Yes` = 成功。

#### B9. 同步 Milvus 数据

```bash
cd /opt/edu_rag

# 从本地同步 Milvus 数据到云上
python scripts/sync_milvus.py \
  --source-host 101.204.208.80 \
  --source-port 19530 \
  --target-host localhost \
  --target-port 19531
```

#### B10. 启动 Nginx（统一入口 + 自动故障转移）

```bash
cd /opt/edu_rag/docker/nginx

# 构建 Nginx 镜像
docker build -t edu_rag_nginx .

# 启动 Nginx（需要先配置 nginx.conf 中的 upstream IP）
# 编辑 nginx.conf，将 LOCAL_PUBLIC_IP 替换为 101.204.208.80
sed -i 's/LOCAL_PUBLIC_IP/101.204.208.80/g' nginx.conf

docker run -d --name edu_rag_nginx \
  --network edu_rag_default \
  -p 80:80 \
  -v $(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro \
  edu_rag_nginx
```

#### B11. 验证健康检查

```bash
# 从云服务器访问（通过 Nginx）
curl http://localhost/health/live
curl http://localhost/health/ready

# 从外网访问
curl http://116.62.121.27/health/live
```

---

### Part C: 配置故障检测（定时任务）

#### C1. 设置定时故障检测

```bash
# 编辑 crontab
crontab -e

# 添加每分钟检测一次
* * * * * cd /opt/edu_rag && python scripts/failover_check.py >> /var/log/edu_rag_failover.log 2>&1
```

#### C2. 设置定时备份

```bash
# 每天凌晨3点备份
0 3 * * * cd /opt/edu_rag && python scripts/backup.py --upload-oss >> /var/log/edu_rag_backup.log 2>&1
```

---

## 验证清单

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| frp 隧道 | `curl http://116.62.121.27:7500` | 仪表盘可访问 |
| MySQL 主从 | `SHOW REPLICA STATUS\G` | IO+SQL Running: Yes |
| 健康检查 | `curl http://116.62.121.27/health/live` | `{"status":"ok"}` |
| Nginx 入口 | 浏览器访问 `http://116.62.121.27` | 跳转到本地 |
| 容器状态 | `docker ps` | 所有容器 Up |

---

## 故障转移流程

### 自动故障转移

`failover_check.py` 每分钟检测本地健康状态，连续 3 次失败后：

1. Nginx 自动切流量到云上 App
2. MySQL 从库提升为主库（可选）
3. 发送告警通知

### 手动故障转移

```bash
cd /opt/edu_rag

# 手动切换 Nginx 到云上
python scripts/failover_check.py --force-failover

# 手动提升 MySQL 从库为主库
python scripts/mysql_promote.py
```

### 故障恢复（failback）

```bash
# 1. 本地恢复后，重新建立主从复制（云→本地）
python scripts/mysql_replication_setup.py \
  --master-host localhost \
  --slave-host 116.62.121.27

# 2. 切换 Nginx 回本地
python scripts/failover_check.py --force-recover
```

---

## 常见问题

### Q: frp 连接失败？
- 检查云服务器安全组是否放行 7000 端口
- 检查 token 是否两端一致
- 查看日志: `docker logs edu_rag_frps` / `docker logs edu_rag_frpc`

### Q: MySQL 主从复制失败？
- 确认本地 MySQL 允许 root 远程连接
- 确认 binlog 已开启（`server.cnf` 中 `log-bin=mysql-bin`）
- 查看错误: `SHOW REPLICA STATUS\G` 中的 `Last_IO_Error`

### Q: 内存不足（OOM）？
- 确认 swap 已配置: `free -h`
- 查看容器内存: `docker stats`
- 临时停止 Milvus: `docker stop edu_rag_milvus_cloud`

### Q: 本地公网 IP 变了？
```bash
# 本地执行，查询新 IP
curl ifconfig.me

# 更新云上配置
sed -i 's/旧IP/新IP/g' /opt/edu_rag/docker/nginx/nginx.conf
sed -i 's/旧IP/新IP/g' /opt/edu_rag/.env.cloud
docker restart edu_rag_nginx
```

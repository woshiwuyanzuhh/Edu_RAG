# edu_rag 云服务器部署清单（P0-DR7 — 阿里云版）

> **当前部署**: ✅ 已上线（2026-07-19）
> - 服务器: 阿里云轻量 2C4G，50GB，杭州，Ubuntu 22.04
> - 公网 IP: `116.62.121.27`
> - 内存优化: 4GB swap + 4GB 优化版 compose

## 服务器选型建议（阿里云轻量应用服务器）

| 配置 | 规格 | 适用场景 | 新用户价 | 续费价 |
|------|------|---------|---------|--------|
| 最低可用 | 2C4G 60G SSD 3Mbps | 纯热备，低并发 | ¥60/月 | ¥106/月 |
| 入门推荐 | 2C4G 80G SSD 4Mbps | 热备+少量并发 | ¥80/月 | ¥140/月 |
| **推荐** | 4C8G 100G SSD 5Mbps | standalone Milvus，稳定运行 | ¥180/月 | ¥240/月 |
| 理想 | 4C8G 200G SSD 6Mbps | 大向量库，高并发 | ¥240/月 | ¥320/月 |

> 阿里云轻量服务器新用户首年通常有 3-5 折优惠，建议趁活动购买。
> 购买地址：https://www.aliyun.com/product/swas
> 地域选择：与用户群体就近（华东→杭州/上海，华南→深圳，华北→北京）

### 为什么选轻量服务器而非 ECS？

| 对比项 | 轻量应用服务器 | ECS |
|--------|--------------|-----|
| 价格 | 便宜 30-50% ✅ | 贵 |
| 流量 | 包含流量包 ✅ | 按量计费 |
| 带宽 | 固定带宽 ✅ | 需单独购买 |
| 适用 | 单机部署 ✅ | 集群部署 |
| SLB | 不支持 ❌ | 支持 |
| 快照 | 支持 ✅ | 支持 |

> 你的项目是单机热备部署，轻量服务器完全够用。

---

## 部署步骤（完整流程）

### Step 1: 服务器初始化

```bash
# SSH 登录云服务器
ssh root@your-cloud-server

# 下载并执行初始化脚本
curl -fsSL scripts/cloud_init.sh | bash
```

### Step 1.5: 配置阿里云 RAM 子账号（可选但推荐）

容灾脚本需要阿里云 API 权限来执行 DNS 切换、OSS 上传、云监控上报。

```bash
# 1. 登录阿里云控制台 → RAM 访问控制 → 用户 → 创建用户
#    用户名：edu_rag_dr
#    勾选：OpenAPI 调用访问
#    保存 AccessKey ID 和 Secret

# 2. 授予权限（最小权限原则）：
#    - AliyunDNSFullAccess       （DNS 流量切换）
#    - AliyunOSSFullAccess       （备份上传 OSS）
#    - AliyunCloudMonitorFullAccess （云监控指标上报）
#    - AliyunLighthouseFullAccess   （轻量服务器快照）

# 3. 在服务器上配置凭证
vi /opt/edu_rag/.aliyun_env
# 填入 AccessKey ID / Secret / Region 等
chmod 600 /opt/edu_rag/.aliyun_env
```

> ⚠️ 不要使用主账号 AccessKey！主账号有全部权限，泄露风险极大。
> RAM 子账号可以随时禁用，且仅有限权限。

### Step 2: 部署项目代码

```bash
cd /opt/edu_rag
git clone <your-repo-url> .

# 或者从本地上传
# scp -r . root@cloud-server:/opt/edu_rag/
```

### Step 3: 配置环境变量

```bash
cp docker/.env.cloud.example .env.cloud
vi .env.cloud
# 填入所有 CHANGE_ME 值
```

**必须修改的项**：
- `MYSQL_PASSWORD` — 强密码（≥16 字符）
- `REDIS_PASSWORD` — 强密码（≥16 字符）
- `OPENAI_API_KEY` — DeepSeek API Key
- `LOCAL_PUBLIC_IP` — 你本地服务器的公网 IP
- `NGINX_LOCAL_HOST` — 同上

### Step 4: 启动云上备机

```bash
cd /opt/edu_rag
docker compose -f docker/docker-compose.cloud.yml --env-file .env.cloud up -d

# 验证
docker compose -f docker/docker-compose.cloud.yml ps
curl http://localhost:8100/health
```

### Step 5: 配置 MySQL 主从复制

**在本地服务器上**：
```bash
python scripts/mysql_replication_setup.py \
    --master-host localhost --master-port 3307 \
    --slave-host <cloud-server-ip> --slave-port 3308 \
    --master-public-ip <your-local-public-ip> \
    --database edu_rag \
    --repl-password <strong-repl-password> \
    --semi-sync
```

### Step 6: 同步 Milvus 向量数据

```bash
python scripts/sync_milvus.py \
    --source-host localhost --source-port 19530 \
    --target-host localhost --target-port 19531 \
    --rebuild
```

> 注意：在云服务器上执行时，source 是本地 Milvus（需公网可达），target 是云上 Milvus。

### Step 7: 配置 Nginx 统一入口

```bash
# 构建 Nginx 镜像
cd /opt/edu_rag
docker build -t edu-rag-nginx -f docker/nginx/Dockerfile .

# 启动 Nginx（替换 LOCAL_HOST 为你的本地公网 IP）
docker run -d --name nginx \
    -p 80:80 \
    -e LOCAL_HOST=<your-local-public-ip> \
    --restart unless-stopped \
    edu-rag-nginx

# 验证
curl http://localhost/nginx-health
curl http://localhost/health
```

### Step 8: 启动故障切换检测

```bash
# 编辑 systemd 服务中的 LOCAL_HOST
sed -i "s/LOCAL_HOST/<your-local-public-ip>/g" /etc/systemd/system/edu-rag-failover.service

# 启动
systemctl daemon-reload
systemctl enable --now edu-rag-failover

# 查看状态
systemctl status edu-rag-failover
journalctl -u edu-rag-failover -f
```

### Step 9: 验证容灾

```bash
# 1. 停止本地 app（模拟故障）
# 在本地: docker compose -f docker/docker-compose.yml stop app

# 2. 在云上观察 failover 检测
journalctl -u edu-rag-failover -f
# 应看到: FAILOVER_TRIGGERED

# 3. 验证流量切到备机
curl http://<cloud-server-ip>/health
# 应返回 200

# 4. 恢复本地
# 在本地: docker compose -f docker/docker-compose.yml start app

# 5. 观察自动切回
journalctl -u edu-rag-failover -f
# 应看到: FAILOVER_RECOVERED
```

---

## 端口规划

| 服务 | 本地端口 | 云上端口 | 说明 |
|------|---------|---------|------|
| App (主) | 8000 | 8100 | Nginx upstream |
| MySQL (主/从) | 3307 | 3308 | 主从复制 |
| Redis (主/从) | 6380 | 6381/6382 | 主从 + Sentinel |
| Sentinel | — | 26379 | Redis 故障转移 |
| Milvus | 19530 | 19531 | 向量库 |
| Ollama | 11434 | 11435 | Embedding |
| Nginx | — | 80 | 统一入口 |

---

## 安全检查清单

- [ ] `.env.cloud` 文件权限设为 600 (`chmod 600 .env.cloud`)
- [ ] MySQL 端口 3308 不对公网开放（仅限本地和 trusted IP）
- [ ] Redis 端口 6381/6382 不对公网开放
- [ ] Milvus 端口 19531 不对公网开放
- [ ] SSH 使用密钥登录，禁用密码登录
- [ ] 防火墙仅开放 22(SSH)、80(HTTP) 端口
- [ ] DeepSeek API Key 不出现在日志中
- [ ] 备份文件加密存储（可选）

---

## 日常运维

| 任务 | 频率 | 命令 |
|------|------|------|
| 数据备份 | 每天 2:00 | 自动（cron） |
| 备份验证 | 每周 | `python scripts/backup_verify.py` |
| 容灾演练 | 每月 | `python scripts/disaster_drill.py` |
| 配置检查 | 每周 | `python scripts/config_drift_check.py` |
| 日志检查 | 每天 | `journalctl -u edu-rag-failover --since "1 hour ago"` |

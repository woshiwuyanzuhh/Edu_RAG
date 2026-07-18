#!/bin/bash
# edu_rag 云服务器初始化脚本（P0-DR7 — 阿里云轻量服务器版）
#
# 在阿里云轻量应用服务器上执行，一键安装所有依赖。
#
# 用法：
#   scp scripts/cloud_init.sh root@your-aliyun-server:~
#   ssh root@your-aliyun-server "bash cloud_init.sh"
#
# 支持的 OS：Ubuntu 22.04+ / Debian 12+
# 针对阿里云优化：
#   1. 使用阿里云内网镜像源（加速 apt/docker/pip）
#   2. 安装阿里云 OSS SDK + DNS SDK + 云监控 SDK
#   3. 配置阿里云 CLI（可选）
set -e

echo "========================================="
echo "  edu_rag 云服务器初始化"
echo "  针对阿里云轻量应用服务器优化"
echo "========================================="
echo ""

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
  echo "❌ 请使用 root 用户执行此脚本"
  exit 1
fi

# 检查 OS
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS=$ID
  OS_VERSION=$VERSION_ID
  echo "OS: $OS $OS_VERSION"
else
  echo "❌ 无法识别操作系统"
  exit 1
fi

# 检测阿里云内网（轻量服务器有 100.100.x.x 内网）
ALIYUN_INTERNAL=false
if curl -s --max-time 2 http://100.100.100.200/latest/meta-data/instance-id &>/dev/null; then
  ALIYUN_INTERNAL=true
  echo "✅ 检测到阿里云内网环境"
  INSTANCE_ID=$(curl -s http://100.100.100.200/latest/meta-data/instance-id)
  REGION=$(curl -s http://100.100.100.200/latest/meta-data/region-id)
  echo "   实例 ID: $INSTANCE_ID"
  echo "   地域: $REGION"
else
  echo "⚠️ 未检测到阿里云内网（可能是其他云厂商或本地 VM）"
fi

# ─── 1. 配置阿里云镜像源（加速）───
echo ""
echo "[1/9] 配置镜像源..."
if [ "$ALIYUN_INTERNAL" = true ]; then
  # 替换 apt 源为阿里云内网镜像
  if [ "$OS" = "ubuntu" ]; then
    sed -i 's|http://.*archive.ubuntu.com|http://mirrors.cloud.aliyuncs.com|g' /etc/apt/sources.list
    sed -i 's|http://.*security.ubuntu.com|http://mirrors.cloud.aliyuncs.com|g' /etc/apt/sources.list
  elif [ "$OS" = "debian" ]; then
    sed -i 's|http://.*deb.debian.org|http://mirrors.cloud.aliyuncs.com|g' /etc/apt/sources.list
  fi
  echo "✅ apt 源已切换到阿里云内网镜像"
fi
apt-get update -qq
apt-get upgrade -y -qq

# ─── 2. 安装 Docker（阿里云加速）───
echo ""
echo "[2/9] 安装 Docker..."
if ! command -v docker &> /dev/null; then
  if [ "$ALIYUN_INTERNAL" = true ]; then
    # 使用阿里云镜像安装 Docker
    curl -fsSL https://mirrors.cloud.aliyuncs.com/docker-ce/linux/ubuntu/gpg | apt-key add -
    add-apt-repository -y "deb [arch=amd64] https://mirrors.cloud.aliyuncs.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable"
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io
  else
    curl -fsSL https://get.docker.com | bash
  fi
  systemctl enable docker
  systemctl start docker

  # 配置 Docker 镜像加速（阿里云专属加速器）
  if [ "$ALIYUN_INTERNAL" = true ] && [ -n "$REGION" ]; then
    ACCELERATOR="https://${REGION}.mirror.aliyuncs.com"
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << EOF
{
  "registry-mirrors": ["${ACCELERATOR}"],
  "log-driver": "json-file",
  "log-opts": { "max-size": "100m", "max-file": "3" }
}
EOF
    systemctl daemon-reload
    systemctl restart docker
    echo "✅ Docker 镜像加速已配置: $ACCELERATOR"
  fi
  echo "✅ Docker 已安装: $(docker --version)"
else
  echo "✅ Docker 已存在: $(docker --version)"
fi

# ─── 3. 安装 Docker Compose ───
echo ""
echo "[3/9] 安装 Docker Compose..."
if docker compose version &> /dev/null; then
  echo "✅ Docker Compose v2 已存在"
else
  apt-get install -y -qq docker-compose-plugin
  echo "✅ Docker Compose v2 已安装"
fi

# ─── 4. 安装 Python 3.12 ───
echo ""
echo "[4/9] 安装 Python 3.12..."
if ! python3.12 --version &> /dev/null; then
  apt-get install -y -qq software-properties-common
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -qq
  apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
  echo "✅ Python 3.12 已安装"
else
  echo "✅ Python 3.12 已存在: $(python3.12 --version)"
fi

# 创建虚拟环境
if [ ! -d /opt/edu_rag/venv ]; then
  python3.12 -m venv /opt/edu_rag/venv
  echo "✅ 虚拟环境已创建: /opt/edu_rag/venv"
fi

# 配置 pip 阿里云镜像
PIP_CONF="/opt/edu_rag/venv/pip.conf"
if [ "$ALIYUN_INTERNAL" = true ] && [ ! -f "$PIP_CONF" ]; then
  mkdir -p /opt/edu_rag/venv
  cat > "$PIP_CONF" << 'EOF'
[global]
index-url = https://mirrors.cloud.aliyuncs.com/pypi/simple/
trusted-host = mirrors.cloud.aliyuncs.com
EOF
  echo "✅ pip 镜像已配置为阿里云内网"
fi

# 安装阿里云 SDK
echo "  安装阿里云 SDK..."
/opt/edu_rag/venv/bin/pip install -q \
  oss2 \
  alibabacloud_alidns20150109 \
  alibabacloud_cms20190101 \
  alibabacloud_lighthouse20201230 2>/dev/null || \
  echo "  ⚠️ 部分阿里云 SDK 安装失败（非必需，仅影响 DNS 切换/OSS 上传功能）"

# ─── 5. 安装 MySQL 客户端 ───
echo ""
echo "[5/9] 安装 MySQL 客户端..."
apt-get install -y -qq mysql-client
echo "✅ mysql-client 已安装: $(mysql --version)"

# ─── 6. 安装 Nginx ───
echo ""
echo "[6/9] 安装 Nginx..."
apt-get install -y -qq nginx
systemctl enable nginx
echo "✅ Nginx 已安装: $(nginx -v 2>&1)"

# ─── 7. 防火墙配置 ───
echo ""
echo "[7/9] 防火墙配置..."
if command -v ufw &> /dev/null; then
  ufw allow 22/tcp    comment "SSH"
  ufw allow 80/tcp    comment "HTTP (Nginx)"
  ufw allow 8100/tcp  comment "edu_rag App (备机)"
  ufw --force enable
  echo "✅ 防火墙已配置"
  echo "   ⚠️ MySQL(3308)/Redis(6381)/Milvus(19531) 仅限 Docker 内网访问，不对公网开放"
  ufw status
else
  echo "⚠️ ufw 未安装，跳过防火墙配置"
  echo "   请在阿里云控制台的安全组中配置规则"
fi

# ─── 8. 创建目录结构 + 配置文件 ───
echo ""
echo "[8/9] 创建目录结构..."
mkdir -p /opt/edu_rag/{data,data/backups,data/drill_reports,logs}
mkdir -p /opt/edu_rag/docker/{nginx,redis,mysql,monitoring}
echo "✅ 目录已创建: /opt/edu_rag/"

# 创建阿里云凭证环境文件
ALIYUN_ENV="/opt/edu_rag/.aliyun_env"
if [ ! -f "$ALIYUN_ENV" ]; then
  cat > "$ALIYUN_ENV" << 'EOF'
# 阿里云凭证（用于 DNS 切换、OSS 上传、云监控）
# 获取方式：阿里云控制台 → RAM 访问控制 → 用户 → 创建 AccessKey
# 权限要求：AliyunDNSFullAccess, AliyunOSSFullAccess, AliyunCloudMonitorFullAccess, AliyunLighthouseFullAccess
export ALIYUN_ACCESS_KEY_ID=
export ALIYUN_ACCESS_KEY_SECRET=
export ALIYUN_REGION=cn-hangzhou
export ALIYUN_OSS_BUCKET=
export ALIYUN_OSS_ENDPOINT=
export ALIYUN_DNS_DOMAIN=
export ALIYUN_DNS_RECORD_ID=
export LOCAL_PUBLIC_IP=
export CLOUD_PUBLIC_IP=
EOF
  echo "✅ 阿里云凭证模板已创建: $ALIYUN_ENV"
  echo "   请编辑填入实际值"
fi

# ─── 9. systemd 服务 + cron ───
echo ""
echo "[9/9] 创建系统服务..."

# failover_check 服务
cat > /etc/systemd/system/edu-rag-failover.service << 'EOF'
[Unit]
Description=edu_rag Failover Check
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/edu_rag
EnvironmentFile=/opt/edu_rag/.aliyun_env
ExecStart=/opt/edu_rag/venv/bin/python scripts/failover_check.py \
    --local-url http://LOCAL_HOST:8000 \
    --backup-url http://127.0.0.1:8100 \
    --nginx-host 127.0.0.1 \
    --interval 5
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
echo "✅ failover_check 服务已创建"

# 备份 cron（含 OSS 上传）
(crontab -l 2>/dev/null | grep -v "edu_rag.*backup"; \
 echo "0 2 * * * cd /opt/edu_rag && /opt/edu_rag/venv/bin/python scripts/backup.py --upload-oss >> /opt/edu_rag/logs/backup.log 2>&1") | crontab -
echo "✅ 每天凌晨 2 点自动备份（含 OSS 上传）"

# 备份验证 cron（每周日）
(crontab -l 2>/dev/null | grep -v "edu_rag.*backup_verify"; \
 echo "0 3 * * 0 cd /opt/edu_rag && /opt/edu_rag/venv/bin/python scripts/backup_verify.py >> /opt/edu_rag/logs/backup_verify.log 2>&1") | crontab -
echo "✅ 每周日凌晨 3 点自动验证备份"

# 配置检查 cron（每周一）
(crontab -l 2>/dev/null | grep -v "edu_rag.*config_drift"; \
 echo "0 4 * * 1 cd /opt/edu_rag && /opt/edu_rag/venv/bin/python scripts/config_drift_check.py --local-url http://localhost:8000 --cloud-url http://localhost:8100 >> /opt/edu_rag/logs/config_drift.log 2>&1") | crontab -
echo "✅ 每周一凌晨 4 点自动检测配置漂移"

# ─── 完成 ───
echo ""
echo "========================================="
echo "  ✅ 阿里云轻量服务器初始化完成！"
echo "========================================="
echo ""
if [ "$ALIYUN_INTERNAL" = true ]; then
  echo "实例信息："
  echo "  实例 ID: $INSTANCE_ID"
  echo "  地域: $REGION"
  echo ""
fi
echo "下一步："
echo "  1. 克隆项目代码: git clone <repo> /opt/edu_rag"
echo "  2. 配置环境变量："
echo "     cp docker/.env.cloud.example .env.cloud && vi .env.cloud"
echo "     vi .aliyun_env  # 填入阿里云 AccessKey"
echo "  3. 启动云上备机:"
echo "     docker compose -f docker/docker-compose.cloud.yml --env-file .env.cloud up -d"
echo "  4. 启动 Nginx（替换 LOCAL_HOST）:"
echo "     docker build -t edu-rag-nginx -f docker/nginx/Dockerfile ."
echo "     docker run -d --name nginx -p 80:80 -e LOCAL_HOST=your.local.ip edu-rag-nginx"
echo "  5. MySQL 主从复制:"
echo "     /opt/edu_rag/venv/bin/python scripts/mysql_replication_setup.py \\"
echo "       --master-host <local-ip> --slave-host 127.0.0.1 \\"
echo "       --slave-port 3308 --repl-password <password>"
echo "  6. Milvus 同步:"
echo "     /opt/edu_rag/venv/bin/python scripts/sync_milvus.py \\"
echo "       --target-host localhost --target-port 19531 --rebuild"
echo "  7. 启动 failover 检测："
echo "     sed -i 's/LOCAL_HOST/<your-local-public-ip>/g' /etc/systemd/system/edu-rag-failover.service"
echo "     systemctl daemon-reload && systemctl enable --now edu-rag-failover"
echo "  8. 验证："
echo "     curl http://localhost/health"
echo "     systemctl status edu-rag-failover"
echo ""
echo "阿里云控制台配置（可选）："
echo "  - 安全组：确认 80 端口已开放"
echo "  - 快照策略：建议设置每日自动快照"
echo "  - 云监控：配置告警联系人"
echo ""

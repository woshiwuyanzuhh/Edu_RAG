#!/bin/bash
# edu_rag frp 配置脚本 — 生成 token 并同步到 frps.toml 和 frpc.toml
#
# 用法：
#   bash scripts/setup_frp.sh
#
# 执行后：
#   1. 生成随机 token（32 字符）
#   2. 替换 docker/frp/frps.toml 中的 token
#   3. 替换 docker/frp/frpc.toml 中的 token 和服务器地址
#   4. 输出配置摘要

set -e

echo "========================================="
echo "  edu_rag frp 配置脚本"
echo "========================================="
echo ""

# 生成随机 token（32 字符）
TOKEN=$(openssl rand -hex 16)
DASHBOARD_PWD=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9' | head -c 16)

echo "[1/4] 生成随机 token: $TOKEN"
echo "      仪表盘密码: $DASHBOARD_PWD"
echo ""

# 配置文件路径
FRPS_TOML="docker/frp/frps.toml"
FRPC_TOML="docker/frp/frpc.toml"

if [ ! -f "$FRPS_TOML" ] || [ ! -f "$FRPC_TOML" ]; then
  echo "❌ 找不到 frp 配置文件，请在项目根目录执行"
  exit 1
fi

# 云服务器 IP（从参数或默认值）
CLOUD_IP="${1:-116.62.121.27}"
echo "[2/4] 云服务器 IP: $CLOUD_IP"
echo ""

# 替换 frps.toml
echo "[3/4] 配置 frps.toml（服务端）..."
sed -i.bak \
  -e "s/auth.token = \"CHANGE_ME_TO_STRONG_TOKEN\"/auth.token = \"$TOKEN\"/" \
  -e "s/webServer.password = \"CHANGE_ME_ADMIN_PASSWORD\"/webServer.password = \"$DASHBOARD_PWD\"/" \
  "$FRPS_TOML"
echo "  ✅ $FRPS_TOML 已更新"

# 替换 frpc.toml
echo "[4/4] 配置 frpc.toml（客户端）..."
sed -i.bak \
  -e "s/auth.token = \"CHANGE_ME_TO_STRONG_TOKEN\"/auth.token = \"$TOKEN\"/" \
  -e "s/serverAddr = \"116.62.121.27\"/serverAddr = \"$CLOUD_IP\"/" \
  "$FRPC_TOML"
echo "  ✅ $FRPC_TOML 已更新"
echo ""

echo "========================================="
echo "  ✅ frp 配置完成"
echo "========================================="
echo ""
echo "服务端配置（云服务器）: docker/frp/frps.toml"
echo "客户端配置（本地）: docker/frp/frpc.toml"
echo ""
echo "云服务器启动 frps:"
echo "  docker compose -f docker/docker-compose.cloud.yml \\"
echo "    -f docker/docker-compose.cloud.4gb.yml \\"
echo "    --env-file .env.cloud up -d frps"
echo ""
echo "本地启动 frpc:"
echo "  docker compose -f docker/docker-compose.frpc.yml up -d"
echo ""
echo "frp 仪表盘: http://$CLOUD_IP:7500"
echo "  用户名: admin"
echo "  密码: $DASHBOARD_PWD"
echo ""
echo "备份文件已保存为 *.bak"

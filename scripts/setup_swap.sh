#!/bin/bash
# edu_rag 4GB 内存优化 — Swap 配置脚本
#
# 在云服务器上执行，创建 4GB swap 文件防止 OOM。
#
# 用法：
#   bash scripts/setup_swap.sh
set -e

echo "========================================="
echo "  edu_rag Swap 配置（4GB 优化）"
echo "========================================="

# 检查 root
if [ "$EUID" -ne 0 ]; then
  echo "❌ 请使用 root 执行"
  exit 1
fi

# 检查当前 swap
CURRENT_SWAP=$(swapon --show --noheadings 2>/dev/null | wc -l)
if [ "$CURRENT_SWAP" -gt 0 ]; then
  echo "⚠️ 已存在 swap:"
  swapon --show
  echo ""
  echo "如需重新配置，请先执行: swapoff -a && rm -f /swapfile"
  exit 0
fi

echo ""
echo "[1/4] 创建 4GB swap 文件..."
# 使用 dd 创建（fallocate 在某些文件系统不支持）
dd if=/dev/zero of=/swapfile bs=1M count=4096 status=progress
chmod 600 /swapfile

echo ""
echo "[2/4] 格式化为 swap..."
mkswap /swapfile

echo ""
echo "[3/4] 启用 swap..."
swapon /swapfile

echo ""
echo "[4/4] 设置开机自动挂载..."
if ! grep -q "/swapfile" /etc/fstab; then
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

# 优化 swappiness（10 = 优先用物理内存，最后才用 swap）
sysctl vm.swappiness=10
if ! grep -q "vm.swappiness" /etc/sysctl.conf; then
  echo "vm.swappiness=10" >> /etc/sysctl.conf
fi

# 验证
echo ""
echo "========================================="
echo "  ✅ Swap 配置完成"
echo "========================================="
echo ""
free -h
echo ""
swapon --show
echo ""
echo "swappiness = $(cat /proc/sys/vm/swappiness) (10=优先物理内存)"

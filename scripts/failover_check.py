"""故障切换检测脚本（P0-DR6 — 增强，含阿里云对接）。

增强功能（对比 v1）：
    1. 多目标探活：本地 + 云上备机同时探活
    2. Nginx 被动健康检查 + 主动 reload：流量自动切换
    3. 阿里云 DNS 切换：配置域名后通过云解析 API 切换（可选）
    4. MySQL 从库提升：触发后自动将从库提升为主库
    5. 告警增强：飞书/钉钉/企业微信 webhook + 阿里云云监控指标
    6. 切换状态记录：记录切换历史，避免重复触发
    7. 恢复检测：本地恢复后自动切回

部署：
    # 常驻循环（推荐）
    nohup python scripts/failover_check.py \
        --local-url http://localhost:8000 \
        --backup-url http://127.0.0.1:8100 \
        --nginx-host 127.0.0.1 \
        --webhook-url https://hooks.example.com/alert \
        --interval 5 &

    # 单次检查（cron 模式）
    python scripts/failover_check.py --once \
        --local-url http://localhost:8000 \
        --backup-url http://127.0.0.1:8100

环境变量：
    FAILOVER_STATE_FILE  — 状态文件路径（默认 /tmp/edu_rag_failover_state.json）
    ALIYUN_DNS_DOMAIN    — 阿里云 DNS 域名（配置后启用 DNS 切换）
    ALIYUN_ACCESS_KEY_ID — 阿里云 AccessKey
    ALIYUN_ACCESS_KEY_SECRET — 阿里云 Secret
    LOCAL_PUBLIC_IP      — 本地公网 IP
    CLOUD_PUBLIC_IP      — 云上备机公网 IP
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("failover")

# 状态文件路径
STATE_FILE = Path(os.getenv("FAILOVER_STATE_FILE", "/tmp/edu_rag_failover_state.json"))


def load_state() -> dict:
    """加载切换状态。"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "current_primary": "local",
        "failover_count": 0,
        "last_failover": None,
        "last_check": None,
        "local_failures": 0,
        "backup_failures": 0,
    }


def save_state(state: dict) -> None:
    """保存切换状态。"""
    state["last_check"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check_health(url: str, timeout: float = 5.0) -> bool:
    """探活 /health 端点（200=健康，503/超时=不健康）。"""
    try:
        import httpx
        r = httpx.get(f"{url}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _try_aliyun_dns_switch(backup_mode: bool) -> None:
    """尝试阿里云 DNS 切换（如果配置了域名和凭证）。"""
    dns_domain = os.getenv("ALIYUN_DNS_DOMAIN", "")
    if not dns_domain:
        return  # 未配置域名，跳过

    try:
        from src.shared.cloud.aliyun import switch_dns_to_backup, switch_dns_to_primary
        target_ip = (
            os.getenv("CLOUD_PUBLIC_IP", "127.0.0.1") if backup_mode
            else os.getenv("LOCAL_PUBLIC_IP", "127.0.0.1")
        )
        if backup_mode:
            switch_dns_to_backup(target_ip, ttl=60)
        else:
            switch_dns_to_primary(target_ip, ttl=600)
    except ImportError:
        logger.debug("[DNS] aliyun 模块未安装，跳过 DNS 切换")
    except Exception as e:
        logger.warning(f"[DNS] 切换异常: {e}")


def switch_nginx_to_backup(nginx_host: str, local_host: str) -> bool:
    """通过 Nginx 切换流量到备机。

    方式1：Nginx 被动健康检查自动切换（默认，无需额外操作）
    方式2：通过 docker exec nginx -s reload 主动触发
    方式3：阿里云 DNS 解析切换（如果配置了域名）
    """
    logger.info(f"[Nginx] 切换流量到备机 (nginx={nginx_host})")

    # 方案1+2：Nginx 被动健康检查会自动切换，主动 reload 加速
    try:
        result = subprocess.run(
            ["docker", "exec", "nginx", "nginx", "-s", "reload"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("[Nginx] reload 成功")
        else:
            logger.warning(f"[Nginx] reload 失败: {result.stderr}")
    except FileNotFoundError:
        logger.warning("[Nginx] docker 命令不可用，依赖被动健康检查自动切换")
    except Exception as e:
        logger.warning(f"[Nginx] reload 异常: {e}")

    # 方案3：阿里云 DNS 切换（如果配置了域名）
    _try_aliyun_dns_switch(backup_mode=True)

    return True  # Nginx 被动健康检查会自动切换


def switch_nginx_to_primary(nginx_host: str) -> bool:
    """将 Nginx 流量切回本地主节点。"""
    logger.info(f"[Nginx] 切回本地主节点 (nginx={nginx_host})")
    # Nginx 被动健康检查会在本地恢复后自动切回
    # 这里主动 reload 并尝试 DNS 切回
    try:
        subprocess.run(
            ["docker", "exec", "nginx", "nginx", "-s", "reload"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        pass

    # 阿里云 DNS 切回
    _try_aliyun_dns_switch(backup_mode=False)
    return True


def promote_mysql_slave(slave_host: str, slave_port: int,
                        slave_user: str, slave_password: str) -> bool:
    """将从库提升为主库（STOP REPLICA + SET read_only=0）。

    仅在 failover 模式为 "promote" 时调用。
    """
    logger.info(f"[MySQL] 提升从库为主库 ({slave_host}:{slave_port})")
    sql = """
        STOP REPLICA;
        SET GLOBAL read_only=0;
        RESET REPLICA ALL;
    """
    try:
        # 通过 mysql 客户端执行
        result = subprocess.run(
            ["mysql",
             f"--host={slave_host}",
             f"--port={slave_port}",
             f"--user={slave_user}",
             f"--password={slave_password}",
             "-e", sql],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("[MySQL] 从库已提升为主库")
            return True
        else:
            logger.error(f"[MySQL] 提升失败: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"[MySQL] 提升异常: {e}")
        return False


def send_alert(webhook_url: str | None, event: str, details: dict) -> None:
    """发送告警 webhook（支持飞书/钉钉/企业微信 + 阿里云云监控）。"""
    if not webhook_url:
        # 即使没有 webhook，也上报阿里云云监控
        _report_aliyun_metric(event, details)
        return

    # 尝试阿里云告警模块（支持飞书/钉钉/企业微信卡片格式）
    sent = False
    try:
        from src.shared.cloud.aliyun import (
            send_feishu_alert, send_dingtalk_alert, send_wechat_alert,
        )

        title = f"edu_rag 容灾告警: {event}"
        content = (
            f"**事件**: {event}\n"
            f"**时间**: {datetime.now().isoformat()}\n"
            f"**详情**:\n```\n{json.dumps(details, ensure_ascii=False, indent=2)}\n```"
        )

        # 根据 webhook URL 判断平台
        if "feishu.cn" in webhook_url or "larksuite" in webhook_url:
            sent = send_feishu_alert(webhook_url, title, content)
        elif "dingtalk.com" in webhook_url:
            sent = send_dingtalk_alert(webhook_url, title, content)
        elif "qyapi.weixin" in webhook_url:
            sent = send_wechat_alert(webhook_url, content)
    except ImportError:
        pass

    # 通用格式（兼容所有平台）
    if not sent:
        payload = {
            "msg_type": "text",
            "content": {
                "text": (
                    f"【edu_rag 容灾告警】\n"
                    f"事件: {event}\n"
                    f"时间: {datetime.now().isoformat()}\n"
                    f"详情: {json.dumps(details, ensure_ascii=False, indent=2)}"
                )
            }
        }
        try:
            import httpx
            httpx.post(webhook_url, json=payload, timeout=10)
            logger.info(f"alert_sent event={event}")
        except Exception as e:
            logger.error(f"alert_failed {e}")

    # 上报阿里云云监控
    _report_aliyun_metric(event, details)


def _report_aliyun_metric(event: str, details: dict) -> None:
    """上报容灾事件到阿里云云监控。"""
    try:
        from src.shared.cloud.aliyun import report_metric
        report_metric("edu_rag_failover_event", 1, {"event": event, **details})
    except ImportError:
        pass
    except Exception:
        pass


def trigger_failover(
    webhook_url: str | None,
    nginx_host: str,
    local_host: str,
    backup_url: str,
    promote_slave: bool,
    slave_cfg: dict | None,
) -> None:
    """触发故障切换：告警 + Nginx 切换 + MySQL 从库提升。"""
    logger.warning("=== FAILOVER_TRIGGERED — 本地不可用，切换流量到备机 ===")

    # 1. 告警
    send_alert(webhook_url, "FAILOVER_TRIGGERED", {
        "reason": "primary unhealthy",
        "backup_url": backup_url,
    })

    # 2. Nginx 流量切换
    switch_nginx_to_backup(nginx_host, local_host)

    # 3. MySQL 从库提升（可选）
    if promote_slave and slave_cfg:
        promote_mysql_slave(
            slave_cfg["host"], slave_cfg["port"],
            slave_cfg["user"], slave_cfg["password"],
        )


def trigger_failback(
    webhook_url: str | None,
    nginx_host: str,
) -> None:
    """本地恢复后切回。"""
    logger.info("=== FAILOVER_RECOVERED — 本地已恢复，切回主节点 ===")

    # 1. 告警
    send_alert(webhook_url, "FAILOVER_RECOVERED", {
        "reason": "primary recovered",
    })

    # 2. Nginx 切回
    switch_nginx_to_primary(nginx_host)


def main() -> int:
    p = argparse.ArgumentParser(description="故障切换检测（增强版）")
    p.add_argument("--local-url", default="http://localhost:8000", help="本地服务地址（主）")
    p.add_argument("--backup-url", default="http://127.0.0.1:8100", help="备机服务地址")
    p.add_argument("--nginx-host", default="127.0.0.1", help="Nginx 主机地址")
    p.add_argument("--local-host", default="localhost", help="本地公网 IP（Nginx upstream 配置用）")
    p.add_argument("--max-failures", type=int, default=3, help="连续失败次数阈值")
    p.add_argument("--recovery-confirm", type=int, default=3, help="恢复确认次数（连续成功后才切回）")
    p.add_argument("--interval", type=float, default=5.0, help="检查间隔（秒）")
    p.add_argument("--webhook-url", default="", help="告警 webhook URL")
    p.add_argument("--promote-slave", action="store_true", help="failover 时提升 MySQL 从库为主库")
    p.add_argument("--slave-host", default="", help="MySQL 从库 host（--promote-slave 时使用）")
    p.add_argument("--slave-port", type=int, default=3306, help="MySQL 从库端口")
    p.add_argument("--slave-user", default="root", help="MySQL 从库用户")
    p.add_argument("--slave-password", default="", help="MySQL 从库密码")
    p.add_argument("--once", action="store_true", help="单次检查后退出（适合 cron）")
    args = p.parse_args()

    slave_cfg = None
    if args.promote_slave and args.slave_host:
        slave_cfg = {
            "host": args.slave_host,
            "port": args.slave_port,
            "user": args.slave_user,
            "password": args.slave_password,
        }

    state = load_state()
    recovery_count = 0

    logger.info(f"故障切换检测启动 | local={args.local_url} backup={args.backup_url} interval={args.interval}s")

    while True:
        local_ok = check_health(args.local_url)
        backup_ok = check_health(args.backup_url) if args.backup_url else True

        if local_ok:
            if state["local_failures"] > 0:
                logger.info(f"local_recovered after {state['local_failures']} failures")

            state["local_failures"] = 0

            # 如果当前在备机模式，检查是否可以切回
            if state["current_primary"] == "backup":
                recovery_count += 1
                logger.info(f"recovery_confirm {recovery_count}/{args.recovery_confirm}")
                if recovery_count >= args.recovery_confirm:
                    trigger_failback(args.webhook_url or None, args.nginx_host)
                    state["current_primary"] = "local"
                    state["failover_count"] += 1
                    state["last_failover"] = datetime.now().isoformat()
                    recovery_count = 0
            else:
                logger.debug("local_healthy")
        else:
            state["local_failures"] += 1
            recovery_count = 0  # 重置恢复计数
            logger.warning(
                f"local_check_failed count={state['local_failures']}/{args.max_failures} "
                f"backup_healthy={backup_ok}"
            )

            if state["local_failures"] >= args.max_failures and state["current_primary"] == "local":
                if backup_ok:
                    trigger_failover(
                        args.webhook_url or None,
                        args.nginx_host,
                        args.local_host,
                        args.backup_url,
                        args.promote_slave,
                        slave_cfg,
                    )
                    state["current_primary"] = "backup"
                    state["failover_count"] += 1
                    state["last_failover"] = datetime.now().isoformat()
                else:
                    logger.error("BOTH_DOWN — 本地和备机都不可用！")
                    send_alert(args.webhook_url or None, "BOTH_DOWN", {
                        "local_url": args.local_url,
                        "backup_url": args.backup_url,
                    })

        save_state(state)

        if args.once:
            return 0 if local_ok else 1

        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())

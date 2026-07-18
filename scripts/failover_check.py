"""故障切换检测脚本（P1-D8）。

定时探活本地 /health（P0-C8 已实现依赖探活），连续 N 次失败触发切换：
1. 调用云 LB API / DNS API 将流量切到备机
2. 发送告警 webhook

部署：
    cron 每 5s 执行：  python scripts/failover_check.py --once --local-url http://localhost:8000 ...
    或常驻循环：       python scripts/failover_check.py --local-url http://localhost:8000 --interval 5

注意：实际切换动作依赖云厂商 LB/DNS API，本脚本提供触发点，
      需按实际云厂商（阿里云/腾讯云/AWS）填充 trigger_failover 实现。
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("failover")


def check_health(url: str, timeout: float = 5.0) -> bool:
    """探活 /health 端点（200=健康，503/超时=不健康）。"""
    try:
        import httpx
        r = httpx.get(f"{url}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def trigger_failover(webhook_url: str | None, dns_api: str | None, dns_token: str | None) -> None:
    """触发故障切换：告警 + DNS/LB 切换。"""
    logger.warning("FAILOVER_TRIGGERED — 本地不可用，切换流量到备机")

    # 1. 告警 webhook（飞书/钉钉/企业微信机器人）
    if webhook_url:
        try:
            import httpx
            httpx.post(webhook_url, json={
                "event": "failover",
                "reason": "primary unhealthy",
                "timestamp": time.time(),
            }, timeout=10)
            logger.info("alert_webhook_sent")
        except Exception as e:
            logger.error(f"webhook_failed {e}")

    # 2. DNS/LB 切换（按云厂商实现，以下是示例骨架）
    if dns_api and dns_token:
        try:
            import httpx
            # 示例：调用 DNS 提供商 API 将域名解析切到备机 IP
            # 实际需按阿里云/腾讯云/AWS 的 API 填充
            httpx.post(
                dns_api,
                headers={"Authorization": f"Bearer {dns_token}"},
                json={"action": "switch_to_backup"},
                timeout=10,
            )
            logger.info("dns_switched_to_backup")
        except Exception as e:
            logger.error(f"dns_switch_failed {e}")


def main() -> int:
    p = argparse.ArgumentParser(description="故障切换检测")
    p.add_argument("--local-url", default="http://localhost:8000", help="本地服务地址")
    p.add_argument("--max-failures", type=int, default=3, help="连续失败次数阈值")
    p.add_argument("--interval", type=float, default=5.0, help="检查间隔（秒）")
    p.add_argument("--webhook-url", default="", help="告警 webhook URL")
    p.add_argument("--dns-api", default="", help="DNS 切换 API URL")
    p.add_argument("--dns-token", default="", help="DNS API token")
    p.add_argument("--once", action="store_true", help="单次检查后退出（适合 cron）")
    args = p.parse_args()

    failures = 0
    while True:
        ok = check_health(args.local_url)
        if ok:
            if failures > 0:
                logger.info(f"primary_recovered after {failures} failures")
            failures = 0
            logger.debug("primary_healthy")
        else:
            failures += 1
            logger.warning(f"primary_check_failed count={failures}/{args.max_failures}")
            if failures >= args.max_failures:
                trigger_failover(
                    args.webhook_url or None,
                    args.dns_api or None,
                    args.dns_token or None,
                )
                failures = 0  # 触发后重置，避免重复触发

        if args.once:
            return 0 if ok else 1
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())

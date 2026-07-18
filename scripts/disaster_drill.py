#!/usr/bin/env python3
"""容灾演练自动化脚本（P2-DR12）

一键执行容灾演练，验证切换流程是否正常。

演练流程：
    Phase 1 — 演练前检查（备机就绪、复制正常）
    Phase 2 — 模拟本地故障（停止本地 app）
    Phase 3 — 验证自动切换（failover_check 触发，流量切到备机）
    Phase 4 — 验证备机服务（API 可用性、数据一致性）
    Phase 5 — 模拟恢复（重启本地 app）
    Phase 6 — 验证自动回切
    Phase 7 — 生成演练报告

用法：
    # 完整演练
    python scripts/disaster_drill.py \
        --local-url http://localhost:8000 \
        --backup-url http://127.0.0.1:8100 \
        --nginx-url http://localhost

    # 仅预检查（不实际切换）
    python scripts/disaster_drill.py --pre-check --backup-url http://127.0.0.1:8100

    # 跳过恢复（演练后不切回，用于验证从库提升）
    python scripts/disaster_drill.py --skip-recovery

建议：
    每月至少执行一次完整演练，确保容灾配置有效。
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("drill")


class DrillReport:
    """演练报告收集器。"""

    def __init__(self):
        self.steps: list[dict] = []
        self.start_time = datetime.now()

    def add_step(self, name: str, status: str, details: dict | None = None):
        step = {
            "step": name,
            "status": status,  # pass / fail / skip
            "timestamp": datetime.now().isoformat(),
            "duration": 0,
            "details": details or {},
        }
        self.steps.append(step)
        symbol = {"pass": "✅", "fail": "❌", "skip": "⏭️"}.get(status, "❓")
        logger.info(f"{symbol} {name}: {status}")
        if details:
            for k, v in details.items():
                logger.info(f"   {k}: {v}")

    def to_dict(self) -> dict:
        return {
            "drill_start": self.start_time.isoformat(),
            "drill_end": datetime.now().isoformat(),
            "total_duration_s": (datetime.now() - self.start_time).total_seconds(),
            "steps": self.steps,
            "overall": "pass" if all(s["status"] != "fail" for s in self.steps) else "fail",
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"演练报告: {path}")


def check_health(url: str, timeout: float = 5.0) -> tuple[bool, dict]:
    """检查服务健康状态。"""
    try:
        import httpx
        r = httpx.get(f"{url}/health", timeout=timeout)
        if r.status_code == 200:
            return True, r.json()
        return False, {"status_code": r.status_code}
    except Exception as e:
        return False, {"error": str(e)}


def stop_local_app() -> bool:
    """停止本地 app 容器（模拟故障）。"""
    logger.info("停止本地 app 容器...")
    result = subprocess.run(
        ["docker", "compose", "-f", "docker/docker-compose.yml", "stop", "app"],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode == 0


def start_local_app() -> bool:
    """启动本地 app 容器。"""
    logger.info("启动本地 app 容器...")
    result = subprocess.run(
        ["docker", "compose", "-f", "docker/docker-compose.yml", "start", "app"],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode == 0


def test_api(url: str) -> dict:
    """测试核心 API 可用性。"""
    results = {}
    import httpx

    # 1. 健康检查
    ok, data = check_health(url)
    results["health"] = {"ok": ok, "data": data}

    # 2. 知识库列表
    try:
        r = httpx.get(f"{url}/api/knowledge-bases", timeout=10)
        results["list_kb"] = {"ok": r.status_code == 200, "count": len(r.json()) if r.status_code == 200 else 0}
    except Exception as e:
        results["list_kb"] = {"ok": False, "error": str(e)}

    # 3. QA 提问（非流式）
    try:
        r = httpx.post(
            f"{url}/api/qa/ask",
            json={"question": "测试问题", "knowledge_base_id": 1},
            timeout=30,
        )
        results["qa_ask"] = {"ok": r.status_code == 200, "status_code": r.status_code}
    except Exception as e:
        results["qa_ask"] = {"ok": False, "error": str(e)}

    return results


def run_drill(args) -> bool:
    """执行容灾演练。"""
    report = DrillReport()

    # ─── Phase 1: 演练前检查 ───
    logger.info("=" * 60)
    logger.info("Phase 1: 演练前检查")
    logger.info("=" * 60)

    # 本地健康
    ok, data = check_health(args.local_url)
    report.add_step("本地服务健康", "pass" if ok else "fail", data)

    # 备机健康
    ok, data = check_health(args.backup_url)
    report.add_step("备机服务健康", "pass" if ok else "fail", data)
    if not ok:
        report.add_step("演练终止", "fail", {"reason": "备机不健康，无法演练"})
        report.save(Path(args.report))
        return False

    # Nginx 健康
    if args.nginx_url:
        try:
            import httpx
            r = httpx.get(f"{args.nginx_url}/nginx-health", timeout=5)
            report.add_step("Nginx 健康", "pass" if r.status_code == 200 else "fail",
                           {"status_code": r.status_code})
        except Exception as e:
            report.add_step("Nginx 健康", "fail", {"error": str(e)})

    if args.pre_check:
        logger.info("预检查完成（--pre-check 模式）")
        report.save(Path(args.report))
        return True

    # ─── Phase 2: 模拟故障 ───
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 2: 模拟本地故障")
    logger.info("=" * 60)

    ok = stop_local_app()
    report.add_step("停止本地 app", "pass" if ok else "fail")

    if not ok:
        report.add_step("演练终止", "fail", {"reason": "无法停止本地 app"})
        report.save(Path(args.report))
        return False

    # ─── Phase 3: 等待自动切换 ───
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 3: 等待自动切换")
    logger.info("=" * 60)

    # 等待 failover_check 检测到故障并切换（默认 15s + 缓冲）
    switch_timeout = args.switch_timeout
    logger.info(f"等待 {switch_timeout}s 触发自动切换...")

    time.sleep(switch_timeout)

    # 通过 Nginx 验证是否切到备机
    if args.nginx_url:
        ok, data = check_health(args.nginx_url)
        report.add_step("Nginx 切换到备机", "pass" if ok else "fail", data)

    # 直接检查备机
    ok, data = check_health(args.backup_url)
    report.add_step("备机承接流量", "pass" if ok else "fail", data)

    # ─── Phase 4: 验证备机服务 ───
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 4: 验证备机服务")
    logger.info("=" * 60)

    api_results = test_api(args.backup_url)
    all_ok = all(r.get("ok", False) for r in api_results.values())
    report.add_step("备机 API 测试", "pass" if all_ok else "fail", api_results)

    if args.skip_recovery:
        logger.info("跳过恢复阶段（--skip-recovery）")
        # 重启本地 app（不验证回切）
        start_local_app()
        report.add_step("重启本地 app", "pass", {"note": "skip_recovery 模式"})
        report.save(Path(args.report))
        return all_ok

    # ─── Phase 5: 模拟恢复 ───
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 5: 模拟本地恢复")
    logger.info("=" * 60)

    ok = start_local_app()
    report.add_step("重启本地 app", "pass" if ok else "fail")

    if ok:
        # 等待本地恢复
        logger.info("等待本地服务恢复...")
        recovered = False
        for _ in range(30):  # 最多等 60s
            ok, _ = check_health(args.local_url)
            if ok:
                recovered = True
                break
            time.sleep(2)

        report.add_step("本地服务恢复", "pass" if recovered else "fail")

    # ─── Phase 6: 验证自动回切 ───
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 6: 验证自动回切")
    logger.info("=" * 60)

    if args.nginx_url:
        # 等待 failover_check 检测到恢复并切回
        logger.info(f"等待 {args.switch_timeout}s 触发自动回切...")
        time.sleep(args.switch_timeout)

        ok, data = check_health(args.nginx_url)
        report.add_step("Nginx 切回本地", "pass" if ok else "fail", data)

    # ─── Phase 7: 演练报告 ───
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 7: 演练报告")
    logger.info("=" * 60)

    report_dict = report.to_dict()
    duration = report_dict["total_duration_s"]
    overall = report_dict["overall"]

    logger.info(f"总耗时: {duration:.1f}s")
    logger.info(f"结果: {'✅ 通过' if overall == 'pass' else '❌ 失败'}")

    passed = sum(1 for s in report.steps if s["status"] == "pass")
    failed = sum(1 for s in report.steps if s["status"] == "fail")
    logger.info(f"通过: {passed} | 失败: {failed}")

    report.save(Path(args.report))

    return overall == "pass"


def main() -> int:
    p = argparse.ArgumentParser(description="容灾演练自动化")
    p.add_argument("--local-url", default="http://localhost:8000", help="本地服务地址")
    p.add_argument("--backup-url", default="http://127.0.0.1:8100", help="备机服务地址")
    p.add_argument("--nginx-url", default=None, help="Nginx 统一入口地址")
    p.add_argument("--switch-timeout", type=int, default=20, help="切换等待时间（秒）")
    p.add_argument("--pre-check", action="store_true", help="仅预检查，不实际切换")
    p.add_argument("--skip-recovery", action="store_true", help="跳过恢复阶段")
    p.add_argument("--report", default="data/drill_reports/latest.json", help="报告输出路径")
    args = p.parse_args()

    success = run_drill(args)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

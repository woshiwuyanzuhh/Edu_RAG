#!/usr/bin/env python3
"""MySQL 从库提升为主库脚本（P2-DR13）

在容灾切换时，将从库提升为独立主库，承接写请求。

操作流程：
    1. 停止复制（STOP REPLICA）
    2. 清除复制配置（RESET REPLICA ALL）
    3. 关闭只读模式（SET GLOBAL read_only=0）
    4. 验证写入测试
    5. 记录提升操作（用于后续回切时重建复制）

回切流程（reverse_promote.py）：
    1. 从新主库导出数据
    2. 在旧主库上恢复数据
    3. 重新建立主从复制（新主 → 旧从）

用法：
    # 提升从库为主库
    python scripts/mysql_promote.py \
        --host cloud-server --port 3308 \
        --user root --password <password>

    # 提升后验证写入
    python scripts/mysql_promote.py --host cloud-server --port 3308 --verify-only

安全注意：
    - 提升操作不可逆（RESET REPLICA ALL 会清除复制位置）
    - 提升前建议先 STOP REPLICA 确认复制已追平
    - 提升后旧主库恢复时需要重新同步数据
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
logger = logging.getLogger("mysql_promote")


def run_mysql(host: str, port: int, user: str, password: str,
              sql: str | None = None, timeout: int = 30) -> tuple[int, str, str]:
    """执行 MySQL 命令，返回 (returncode, stdout, stderr)。"""
    cmd = [
        "mysql",
        f"--host={host}",
        f"--port={port}",
        f"--user={user}",
        f"--password={password}",
        "--default-character-set=utf8mb4",
    ]
    if sql:
        cmd.extend(["-e", sql])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


def check_replica_status(host: str, port: int, user: str, password: str) -> dict:
    """检查从库复制状态。"""
    rc, stdout, _ = run_mysql(host, port, user, password,
                             sql="SHOW REPLICA STATUS\\G")
    status = {}
    for line in stdout.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            status[key] = val
    return status


def check_is_readonly(host: str, port: int, user: str, password: str) -> bool:
    """检查是否处于只读模式。"""
    rc, stdout, _ = run_mysql(host, port, user, password,
                             sql="SELECT @@global.read_only")
    lines = stdout.strip().split("\n")
    if len(lines) > 1:
        return lines[1].strip() == "1"
    return False


def promote_to_master(host: str, port: int, user: str, password: str) -> dict:
    """将从库提升为主库。

    Returns:
        操作结果
    """
    result = {
        "promoted_at": datetime.now().isoformat(),
        "host": host,
        "port": port,
        "steps": [],
    }

    # Step 1: 检查当前复制状态
    logger.info("[1/5] 检查当前复制状态...")
    status = check_replica_status(host, port, user, password)

    if not status:
        logger.warning("未找到复制状态信息（可能已是独立主库）")
        result["steps"].append({"step": "check_replica", "status": "skip", "reason": "no replica config"})
    else:
        io_running = status.get("Replica_IO_Running", "No")
        sql_running = status.get("Replica_SQL_Running", "No")
        seconds_behind = status.get("Seconds_Behind_Master", "NULL")

        logger.info(f"  IO: {io_running}, SQL: {sql_running}, Lag: {seconds_behind}s")
        result["steps"].append({
            "step": "check_replica",
            "status": "pass",
            "io_running": io_running,
            "sql_running": sql_running,
            "seconds_behind": seconds_behind,
        })

        # 等待复制追平
        if io_running == "Yes" and seconds_behind != "0" and seconds_behind != "NULL":
            logger.info("等待复制追平...")
            for _ in range(30):
                time.sleep(1)
                status = check_replica_status(host, port, user, password)
                seconds_behind = status.get("Seconds_Behind_Master", "NULL")
                if seconds_behind == "0" or seconds_behind == "NULL":
                    break
            logger.info(f"复制延迟: {seconds_behind}s")

    # Step 2: STOP REPLICA
    logger.info("[2/5] STOP REPLICA...")
    rc, _, stderr = run_mysql(host, port, user, password, sql="STOP REPLICA")
    if rc != 0 and "Warning" not in stderr:
        logger.warning(f"STOP REPLICA: {stderr}")
    result["steps"].append({"step": "stop_replica", "status": "pass" if rc == 0 else "warn"})

    # Step 3: SET GLOBAL read_only=0
    logger.info("[3/5] SET GLOBAL read_only=0...")
    rc, _, stderr = run_mysql(host, port, user, password, sql="SET GLOBAL read_only=0")
    if rc != 0:
        logger.error(f"关闭只读失败: {stderr}")
        result["steps"].append({"step": "disable_readonly", "status": "fail", "error": stderr})
        return result
    result["steps"].append({"step": "disable_readonly", "status": "pass"})

    # Step 4: RESET REPLICA ALL（清除复制配置）
    logger.info("[4/5] RESET REPLICA ALL...")
    rc, _, stderr = run_mysql(host, port, user, password, sql="RESET REPLICA ALL")
    if rc != 0 and "Warning" not in stderr:
        logger.warning(f"RESET REPLICA ALL: {stderr}")
    result["steps"].append({"step": "reset_replica", "status": "pass" if rc == 0 else "warn"})

    # Step 5: 验证
    logger.info("[5/5] 验证提升结果...")
    is_readonly = check_is_readonly(host, port, user, password)
    if is_readonly:
        logger.error("❌ 仍处于只读模式！")
        result["steps"].append({"step": "verify", "status": "fail", "read_only": True})
    else:
        logger.info("✅ 已提升为主库（read_only=0）")
        result["steps"].append({"step": "verify", "status": "pass", "read_only": False})

    # 写入提升记录（用于后续回切重建复制）
    record_file = Path(f"/tmp/edu_rag_promote_{int(time.time())}.json")
    try:
        record_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"提升记录: {record_file}")
    except Exception:
        pass

    return result


def verify_write(host: str, port: int, user: str, password: str, database: str) -> bool:
    """验证写入能力。"""
    logger.info("验证写入能力...")

    # 创建临时表并写入
    sql = f"""
        USE {database};
        CREATE TABLE IF NOT EXISTS _promote_test (
            id INT PRIMARY KEY,
            msg VARCHAR(100),
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO _promote_test (id, msg) VALUES (1, 'promote_verify');
        SELECT * FROM _promote_test;
        DROP TABLE _promote_test;
    """
    rc, stdout, stderr = run_mysql(host, port, user, password, sql=sql)
    if rc == 0 and "promote_verify" in stdout:
        logger.info("✅ 写入验证通过")
        return True
    else:
        logger.error(f"❌ 写入验证失败: {stderr}")
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="MySQL 从库提升为主库")
    p.add_argument("--host", required=True, help="MySQL 从库 host")
    p.add_argument("--port", type=int, default=3306, help="端口")
    p.add_argument("--user", default="root", help="用户")
    p.add_argument("--password", default="", help="密码")
    p.add_argument("--database", default="edu_rag", help="数据库")
    p.add_argument("--verify-only", action="store_true", help="仅验证写入能力，不实际提升")
    p.add_argument("--no-confirm", action="store_true", help="跳过确认提示")
    args = p.parse_args()

    if args.verify_only:
        ok = verify_write(args.host, args.port, args.user, args.password, args.database)
        return 0 if ok else 1

    # 确认提示
    if not args.no_confirm:
        print(f"\n⚠️  即将提升 {args.host}:{args.port} 为独立主库！")
        print("   此操作将：")
        print("   1. STOP REPLICA（停止复制）")
        print("   2. SET read_only=0（关闭只读）")
        print("   3. RESET REPLICA ALL（清除复制配置，不可逆）")
        print()
        response = input("确认执行？(yes/no): ")
        if response.lower() != "yes":
            logger.info("已取消")
            return 0

    result = promote_to_master(args.host, args.port, args.user, args.password)

    # 写入验证
    if all(s["status"] != "fail" for s in result["steps"]):
        verify_write(args.host, args.port, args.user, args.password, args.database)

    success = all(s["status"] != "fail" for s in result["steps"])
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

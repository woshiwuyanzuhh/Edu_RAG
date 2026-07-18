#!/usr/bin/env python3
"""MySQL 主从复制初始化脚本（P0-DR2）

自动化完成本地主库 → 云上从库的主从复制配置。

流程：
    Phase 1 — 主库（本地）准备：
        1. 创建复制账号（REPLICATION SLAVE 权限）
        2. 创建全量 dump（--single-transaction）
        3. 获取 binlog 位置（MASTER STATUS）

    Phase 2 — 从库（云上）恢复：
        4. 导入 dump
        5. CHANGE MASTER TO ...（指向主库 IP + binlog 位置）
        6. START REPLICA
        7. 验证复制状态（SHOW REPLICA STATUS）

    Phase 3 — 半同步插件（可选）：
        8. 主从安装半同步插件，降低 RPO 到秒级

用法：
    # 完整初始化（主库 + 从库）
    python scripts/mysql_replication_setup.py \
        --master-host 192.168.1.100 --slave-host cloud-server.example.com \
        --repl-password <强密码>

    # 仅主库准备（dump + binlog 位置输出）
    python scripts/mysql_replication_setup.py --master-only --master-host localhost

    # 仅从库配置（已有 dump 文件）
    python scripts/mysql_replication_setup.py --slave-only \
        --slave-host cloud-server --dump-file /tmp/mysql_dump.sql \
        --master-host 192.168.1.100 --master-log-file mysql-bin.000001 --master-log-pos 12345

前置条件：
    - 主库已挂载 master.cnf（binlog 开启）
    - 从库已挂载 slave.cnf（read-only=1, relay-log）
    - 主库 3306 端口对从库可达
    - mysqldump / mysql 客户端已安装
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mysql_repl")


def run_mysql(host: str, port: int, user: str, password: str, database: str | None,
              sql: str | None = None, stdin_file: str | None = None,
              timeout: int = 600) -> tuple[int, str]:
    """执行 MySQL 命令。

    Returns:
        (returncode, stderr)
    """
    cmd = [
        "mysql",
        f"--host={host}",
        f"--port={port}",
        f"--user={user}",
        f"--password={password}",
        "--default-character-set=utf8mb4",
    ]
    if database:
        cmd.append(database)

    if sql:
        cmd.extend(["-e", sql])

    stdin = None
    if stdin_file:
        stdin = open(stdin_file, encoding="utf-8")

    try:
        result = subprocess.run(
            cmd,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return result.returncode, result.stderr.decode("utf-8", errors="replace")
    finally:
        if stdin:
            stdin.close()


def run_mysqldump(host: str, port: int, user: str, password: str, database: str,
                  output_file: str, timeout: int = 600) -> tuple[int, str]:
    """执行 mysqldump。"""
    cmd = [
        "mysqldump",
        f"--host={host}",
        f"--port={port}",
        f"--user={user}",
        f"--password={password}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--events",
        "--set-gtid-purged=OFF",
        "--column-statistics=0",
        "--master-data=2",  # 在 dump 中注释记录 binlog 位置
        database,
    ]

    with open(output_file, "w", encoding="utf-8") as f:
        result = subprocess.run(
            cmd,
            stdout=f,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    return result.returncode, result.stderr.decode("utf-8", errors="replace")


def phase1_master_prepare(master_cfg: dict, repl_password: str) -> dict:
    """Phase 1: 主库准备 — 创建复制账号 + dump + 记录 binlog 位置。

    Returns:
        {"dump_file": str, "log_file": str, "log_pos": int}
    """
    host = master_cfg["host"]
    port = master_cfg["port"]
    user = master_cfg["user"]
    password = master_cfg["password"]
    database = master_cfg["database"]

    logger.info(f"=== Phase 1: 主库准备 ({host}:{port}) ===")

    # 1. 创建复制账号
    repl_user = "repl"
    logger.info(f"[1/3] 创建复制账号 '{repl_user}'")
    sql = f"""
        CREATE USER IF NOT EXISTS '{repl_user}'@'%' IDENTIFIED BY '{repl_password}';
        GRANT REPLICATION SLAVE ON *.* TO '{repl_user}'@'%';
        FLUSH PRIVILEGES;
    """
    rc, err = run_mysql(host, port, user, password, None, sql=sql)
    if rc != 0 and "Warning" not in err:
        logger.warning(f"创建复制账号返回: {err}")
    logger.info("复制账号已创建/已存在")

    # 2. 全量 dump（--master-data=2 自动记录 binlog 位置）
    dump_file = f"/tmp/edu_rag_master_dump_{int(time.time())}.sql"
    logger.info(f"[2/3] 全量 dump → {dump_file}")
    rc, err = run_mysqldump(host, port, user, password, database, dump_file)
    if rc != 0 and "Warning" not in err:
        logger.error(f"dump 失败: {err}")
        sys.exit(1)

    # 从 dump 文件头部提取 binlog 位置（--master-data=2 写入注释）
    log_file = ""
    log_pos = 0
    with open(dump_file, encoding="utf-8") as f:
        for line in f:
            if "CHANGE MASTER TO MASTER_LOG_FILE" in line:
                # 格式: -- CHANGE MASTER TO MASTER_LOG_FILE='mysql-bin.000001', MASTER_LOG_POS=12345;
                import re
                match = re.search(r"MASTER_LOG_FILE='([^']+)',\s*MASTER_LOG_POS=(\d+)", line)
                if match:
                    log_file = match.group(1)
                    log_pos = int(match.group(2))
                break

    if not log_file:
        # fallback: 直接查询
        logger.info("[2/3] 从 dump 未找到 binlog 位置，直接查询 MASTER STATUS")
        rc, err = run_mysql(host, port, user, password, None,
                           sql="SHOW MASTER STATUS\\G")
        # 注意：mysql -e 输出在 stdout，需要另一种方式
        # 这里简化处理，用 SHOW MASTER STATUS
        result = subprocess.run(
            ["mysql", f"--host={host}", f"--port={port}",
             f"--user={user}", f"--password={password}",
             "-e", "SHOW MASTER STATUS"],
            capture_output=True, text=True, timeout=30,
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) > 1:
            parts = lines[1].split("\t")
            if len(parts) >= 2:
                log_file = parts[0]
                log_pos = int(parts[1])

    logger.info(f"[3/3] binlog 位置: file={log_file} pos={log_pos}")

    return {
        "dump_file": dump_file,
        "log_file": log_file,
        "log_pos": log_pos,
        "repl_user": repl_user,
        "repl_password": repl_password,
    }


def phase2_slave_configure(slave_cfg: dict, master_cfg: dict, master_info: dict,
                           master_public_ip: str) -> bool:
    """Phase 2: 从库配置 — 导入 dump + CHANGE MASTER + START REPLICA。

    Args:
        slave_cfg: 从库连接配置
        master_cfg: 主库连接配置（用于获取凭证）
        master_info: Phase 1 输出 {dump_file, log_file, log_pos, repl_user, repl_password}
        master_public_ip: 主库的公网 IP（从库通过此 IP 连接主库）

    Returns:
        是否成功
    """
    host = slave_cfg["host"]
    port = slave_cfg["port"]
    user = slave_cfg["user"]
    password = slave_cfg["password"]
    database = slave_cfg["database"]

    logger.info(f"=== Phase 2: 从库配置 ({host}:{port}) ===")

    # 4. 导入 dump
    dump_file = master_info["dump_file"]
    if os.path.exists(dump_file):
        logger.info(f"[4/6] 导入 dump → 从库")
        rc, err = run_mysql(host, port, user, password, database, stdin_file=dump_file)
        if rc != 0 and "Warning" not in err:
            logger.error(f"导入 dump 失败: {err}")
            return False
        logger.info("dump 导入成功")
    else:
        logger.warning(f"dump 文件不存在: {dump_file}，跳过导入")

    # 5. CHANGE MASTER TO
    log_file = master_info["log_file"]
    log_pos = master_info["log_pos"]
    repl_user = master_info["repl_user"]
    repl_password = master_info["repl_password"]

    logger.info(f"[5/6] CHANGE MASTER TO (master={master_public_ip}:{master_cfg['port']})")
    sql = f"""
        STOP REPLICA;
        RESET REPLICA ALL;
        CHANGE REPLICATION SOURCE TO
            SOURCE_HOST='{master_public_ip}',
            SOURCE_PORT={master_cfg['port']},
            SOURCE_USER='{repl_user}',
            SOURCE_PASSWORD='{repl_password}',
            SOURCE_LOG_FILE='{log_file}',
            SOURCE_LOG_POS={log_pos},
            SOURCE_CONNECT_RETRY=10,
            GET_SOURCE_PUBLIC_KEY=1;
        START REPLICA;
    """
    rc, err = run_mysql(host, port, user, password, None, sql=sql)
    if rc != 0 and "Warning" not in err:
        logger.error(f"CHANGE MASTER 失败: {err}")
        return False

    # 6. 验证复制状态
    logger.info("[6/6] 验证复制状态...")
    time.sleep(3)  # 等待复制线程启动

    result = subprocess.run(
        ["mysql", f"--host={host}", f"--port={port}",
         f"--user={user}", f"--password={password}",
         "-e", "SHOW REPLICA STATUS\\G"],
        capture_output=True, text=True, timeout=30,
    )

    output = result.stdout
    if "Replica_IO_Running: Yes" in output and "Replica_SQL_Running: Yes" in output:
        logger.info("✅ 复制正常: IO=Yes, SQL=Yes")

        # 提取复制延迟
        for line in output.split("\n"):
            if "Seconds_Behind_Master" in line:
                delay = line.split(":")[-1].strip()
                logger.info(f"   复制延迟: {delay}s")
                break
        return True
    else:
        logger.error("❌ 复制异常:")
        for line in output.split("\n"):
            if "Running" in line or "Error" in line or "Last_IO" in line:
                logger.error(f"   {line.strip()}")
        return False


def phase3_semi_sync(master_cfg: dict, slave_cfg: dict) -> None:
    """Phase 3: 半同步复制插件（降低 RPO 到秒级）。"""
    logger.info("=== Phase 3: 半同步复制（可选）===")

    # 主库
    sql_master = """
        INSTALL PLUGIN IF NOT EXISTS rpl_semi_sync_master SONAME 'semisync_master.so';
        SET GLOBAL rpl_semi_sync_master_enabled = 1;
        SET GLOBAL rpl_semi_sync_master_timeout = 3000;
    """
    rc, err = run_mysql(master_cfg["host"], master_cfg["port"],
                       master_cfg["user"], master_cfg["password"], None, sql=sql_master)
    if rc != 0:
        logger.warning(f"主库半同步插件安装失败（可能已安装或不支持）: {err}")
    else:
        logger.info("主库半同步已启用")

    # 从库
    sql_slave = """
        INSTALL PLUGIN IF NOT EXISTS rpl_semi_sync_slave SONAME 'semisync_slave.so';
        SET GLOBAL rpl_semi_sync_slave_enabled = 1;
        STOP REPLICA IO_THREAD;
        START REPLICA IO_THREAD;
    """
    rc, err = run_mysql(slave_cfg["host"], slave_cfg["port"],
                       slave_cfg["user"], slave_cfg["password"], None, sql=sql_slave)
    if rc != 0:
        logger.warning(f"从库半同步插件安装失败（可能已安装或不支持）: {err}")
    else:
        logger.info("从库半同步已启用")


def main() -> int:
    p = argparse.ArgumentParser(description="MySQL 主从复制初始化")
    p.add_argument("--master-host", required=True, help="主库 host")
    p.add_argument("--master-port", type=int, default=3306, help="主库端口")
    p.add_argument("--master-user", default="root", help="主库用户")
    p.add_argument("--master-password", default=os.getenv("MYSQL_PASSWORD", ""), help="主库密码")
    p.add_argument("--slave-host", default=None, help="从库 host")
    p.add_argument("--slave-port", type=int, default=3306, help="从库端口")
    p.add_argument("--slave-user", default="root", help="从库用户")
    p.add_argument("--slave-password", default=None, help="从库密码（默认与主库相同）")
    p.add_argument("--database", default="edu_rag", help="数据库名")
    p.add_argument("--repl-password", required=True, help="复制账号密码")
    p.add_argument("--master-public-ip", default=None, help="主库公网 IP（从库通过此连接主库）")
    p.add_argument("--master-only", action="store_true", help="仅执行主库准备")
    p.add_argument("--slave-only", action="store_true", help="仅执行从库配置")
    p.add_argument("--dump-file", default=None, help="已有的 dump 文件（--slave-only 模式使用）")
    p.add_argument("--master-log-file", default=None, help="主库 binlog 文件名（--slave-only 模式使用）")
    p.add_argument("--master-log-pos", type=int, default=None, help="主库 binlog 位置（--slave-only 模式使用）")
    p.add_argument("--semi-sync", action="store_true", help="启用半同步复制")
    args = p.parse_args()

    master_cfg = {
        "host": args.master_host,
        "port": args.master_port,
        "user": args.master_user,
        "password": args.master_password,
        "database": args.database,
    }

    slave_cfg = {
        "host": args.slave_host or "",
        "port": args.slave_port,
        "user": args.slave_user,
        "password": args.slave_password or args.master_password,
        "database": args.database,
    }

    master_public_ip = args.master_public_ip or args.master_host

    # Phase 1: 主库准备
    if not args.slave_only:
        master_info = phase1_master_prepare(master_cfg, args.repl_password)
    else:
        if not args.dump_file or not args.master_log_file or not args.master_log_pos:
            logger.error("--slave-only 模式需要 --dump-file, --master-log-file, --master-log-pos")
            return 1
        master_info = {
            "dump_file": args.dump_file,
            "log_file": args.master_log_file,
            "log_pos": args.master_log_pos,
            "repl_user": "repl",
            "repl_password": args.repl_password,
        }

    if args.master_only:
        logger.info("=== 主库准备完成（--master-only）===")
        logger.info(f"dump 文件: {master_info['dump_file']}")
        logger.info(f"binlog 位置: file={master_info['log_file']} pos={master_info['log_pos']}")
        logger.info(f"\n从库执行命令:")
        logger.info(f"python scripts/mysql_replication_setup.py --slave-only \\")
        logger.info(f"    --slave-host <cloud-ip> \\")
        logger.info(f"    --master-host {master_public_ip} \\")
        logger.info(f"    --dump-file {master_info['dump_file']} \\")
        logger.info(f"    --master-log-file {master_info['log_file']} \\")
        logger.info(f"    --master-log-pos {master_info['log_pos']} \\")
        logger.info(f"    --repl-password ***")
        return 0

    # Phase 2: 从库配置
    if not slave_cfg["host"]:
        logger.error("从库 host 未指定（--slave-host）")
        return 1

    success = phase2_slave_configure(slave_cfg, master_cfg, master_info, master_public_ip)
    if not success:
        return 1

    # Phase 3: 半同步（可选）
    if args.semi_sync:
        phase3_semi_sync(master_cfg, slave_cfg)

    logger.info("=== MySQL 主从复制初始化完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

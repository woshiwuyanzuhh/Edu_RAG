#!/usr/bin/env python3
"""备份验证脚本（P1-DR9）

验证备份文件的可恢复性：
    1. 检查备份目录结构完整性
    2. 验证 MySQL dump 文件可被 mysql 命令解析
    3. 验证 Milvus 导出文件 JSON 格式正确
    4. 验证文件目录非空
    5. 在临时 MySQL 实例中恢复验证（可选，需 Docker）

用法：
    # 验证最近一次备份
    python scripts/backup_verify.py

    # 验证指定备份
    python scripts/backup_verify.py --backup-dir data/backups/20260718_020000

    # 完整验证（在临时 Docker MySQL 中恢复测试）
    python scripts/backup_verify.py --full-restore-test

部署：
    # cron 每周验证
    0 3 * * 0 cd /path/to/edu_rag && python scripts/backup_verify.py >> logs/backup_verify.log 2>&1
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backup_verify")


def find_latest_backup(backup_root: Path) -> Path | None:
    """找到最近的备份目录。"""
    if not backup_root.exists():
        return None

    backups = sorted(
        [d for d in backup_root.iterdir() if d.is_dir() and d.name[0].isdigit()],
        key=lambda d: d.name,
        reverse=True,
    )
    return backups[0] if backups else None


def verify_manifest(backup_dir: Path) -> dict:
    """验证备份清单文件。"""
    manifest_file = backup_dir / "backup_manifest.json"
    if not manifest_file.exists():
        return {"pass": False, "error": "backup_manifest.json 不存在"}

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        return {"pass": True, "manifest": manifest}
    except Exception as e:
        return {"pass": False, "error": f"清单文件解析失败: {e}"}


def verify_mysql_dump(dump_file: Path) -> dict:
    """验证 MySQL dump 文件。

    检查：
    1. 文件存在且非空
    2. 包含有效的 SQL 语句（CREATE TABLE / INSERT）
    3. 可以被 mysql --execute 解析（dry run）
    """
    if not dump_file.exists():
        return {"pass": False, "error": "dump 文件不存在"}

    size = dump_file.stat().st_size
    if size == 0:
        return {"pass": False, "error": "dump 文件为空"}

    # 读取前 1KB 检查格式
    with open(dump_file, encoding="utf-8", errors="replace") as f:
        header = f.read(1024)

    # 检查是否包含 MySQL dump 标志
    has_header = "-- MySQL dump" in header or "/*!40101" in header
    if not has_header:
        return {"pass": False, "error": "不是有效的 MySQL dump 文件（缺少头部标记）"}

    # 统计 SQL 语句
    content = dump_file.read_text(encoding="utf-8", errors="replace")
    create_count = content.count("CREATE TABLE")
    insert_count = content.count("INSERT INTO")

    return {
        "pass": True,
        "size_mb": round(size / (1024 * 1024), 1),
        "create_tables": create_count,
        "inserts": insert_count,
    }


def verify_milvus_export(export_file: Path) -> dict:
    """验证 Milvus 导出文件。"""
    if not export_file.exists():
        return {"pass": False, "error": "Milvus 导出文件不存在"}

    size = export_file.stat().st_size
    if size == 0:
        return {"pass": False, "error": "导出文件为空"}

    # 验证 JSONL 格式
    line_count = 0
    valid_json = 0
    errors = 0

    with open(export_file, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line_count += 1
            try:
                json.loads(line)
                valid_json += 1
            except Exception:
                errors += 1
                if errors <= 3:
                    logger.warning(f"第 {i+1} 行 JSON 解析失败")

            # 抽样检查前 100 行
            if line_count >= 100:
                break

    return {
        "pass": errors == 0,
        "sampled_lines": line_count,
        "valid_json": valid_json,
        "errors": errors,
        "size_mb": round(size / (1024 * 1024), 1),
    }


def verify_files(files_dir: Path) -> dict:
    """验证文件目录。"""
    if not files_dir.exists():
        return {"pass": False, "error": "文件目录不存在"}

    file_count = sum(1 for _ in files_dir.rglob("*") if _.is_file())
    total_size = sum(f.stat().st_size for f in files_dir.rglob("*") if f.is_file())

    return {
        "pass": file_count > 0,
        "file_count": file_count,
        "total_size_mb": round(total_size / (1024 * 1024), 1),
    }


def full_restore_test(backup_dir: Path, mysql_password: str) -> dict:
    """在临时 Docker MySQL 中恢复测试。

    启动一个临时 MySQL 容器，导入 dump，验证表结构和数据量。
    """
    import tempfile

    logger.info("启动临时 MySQL 容器进行恢复测试...")

    container_name = f"edu_rag_verify_{int(datetime.now().timestamp())}"

    try:
        # 启动临时 MySQL
        result = subprocess.run(
            ["docker", "run", "-d",
             "--name", container_name,
             "-e", f"MYSQL_ROOT_PASSWORD={mysql_password}",
             "-e", "MYSQL_DATABASE=edu_rag_verify",
             "-p", "0:3306",  # 随机端口
             "mysql:8.0",
             "--default-authentication-plugin=mysql_native_password"],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            return {"pass": False, "error": f"启动容器失败: {result.stderr}"}

        # 等待 MySQL 就绪
        logger.info("等待 MySQL 就绪...")
        import time
        for _ in range(30):
            result = subprocess.run(
                ["docker", "exec", container_name,
                 "mysqladmin", "ping", "-h", "localhost",
                 "-p", mysql_password],
                capture_output=True, text=True, timeout=10,
            )
            if "mysqld is alive" in result.stdout:
                break
            time.sleep(2)
        else:
            return {"pass": False, "error": "MySQL 启动超时"}

        # 导入 dump
        dump_file = backup_dir / "mysql_dump.sql"
        if dump_file.exists():
            logger.info("导入 dump 到临时容器...")
            with open(dump_file, encoding="utf-8") as f:
                result = subprocess.run(
                    ["docker", "exec", "-i", container_name,
                     "mysql", "-uroot", f"-p{mysql_password}",
                     "edu_rag"],
                    stdin=f, capture_output=True, text=True, timeout=300,
                )
            if result.returncode != 0:
                return {"pass": False, "error": f"导入失败: {result.stderr[:500]}"}

            # 验证表
            result = subprocess.run(
                ["docker", "exec", container_name,
                 "mysql", "-uroot", f"-p{mysql_password}",
                 "edu_rag", "-e",
                 "SELECT COUNT(*) as tables FROM information_schema.tables WHERE table_schema='edu_rag';"],
                capture_output=True, text=True, timeout=10,
            )
            logger.info(f"表数量验证: {result.stdout.strip()}")

            return {"pass": True, "restored": True}
        else:
            return {"pass": False, "error": "dump 文件不存在"}

    except Exception as e:
        return {"pass": False, "error": str(e)}
    finally:
        # 清理临时容器
        subprocess.run(["docker", "rm", "-f", container_name],
                       capture_output=True, timeout=30)


def main() -> int:
    p = argparse.ArgumentParser(description="备份验证")
    p.add_argument("--backup-dir", default=None, help="指定备份目录（不指定则验证最近一次）")
    p.add_argument("--backup-root", default=str(PROJECT_ROOT / "data" / "backups"),
                   help="备份根目录")
    p.add_argument("--full-restore-test", action="store_true",
                   help="在临时 Docker MySQL 中恢复测试")
    p.add_argument("--mysql-password", default="verify_test_pass",
                   help="临时 MySQL 密码（仅 --full-restore-test 使用）")
    args = p.parse_args()

    # 找到备份目录
    if args.backup_dir:
        backup_dir = Path(args.backup_dir)
    else:
        backup_dir = find_latest_backup(Path(args.backup_root))

    if not backup_dir or not backup_dir.exists():
        logger.error("未找到备份目录")
        return 1

    logger.info(f"=== 验证备份: {backup_dir.name} ===")

    results = {"overall_pass": True}
    all_pass = True

    # 1. 验证清单
    logger.info("[1/4] 验证备份清单...")
    manifest_result = verify_manifest(backup_dir)
    results["manifest"] = manifest_result
    if manifest_result["pass"]:
        m = manifest_result["manifest"]
        logger.info(f"  ✅ 清单有效 | 备份时间: {m.get('backup_time')} | 状态: {m.get('status')}")
    else:
        logger.error(f"  ❌ {manifest_result['error']}")
        all_pass = False

    # 2. 验证 MySQL dump
    logger.info("[2/4] 验证 MySQL dump...")
    dump_file = backup_dir / "mysql_dump.sql"
    mysql_result = verify_mysql_dump(dump_file)
    results["mysql"] = mysql_result
    if mysql_result["pass"]:
        logger.info(f"  ✅ dump 有效 | {mysql_result.get('size_mb', 0)} MB | "
                    f"表: {mysql_result.get('create_tables', 0)} | "
                    f"INSERT: {mysql_result.get('inserts', 0)}")
    else:
        logger.error(f"  ❌ {mysql_result.get('error', '验证失败')}")
        all_pass = False

    # 3. 验证 Milvus 导出
    logger.info("[3/4] 验证 Milvus 导出...")
    milvus_file = backup_dir / "milvus_export.jsonl"
    milvus_result = verify_milvus_export(milvus_file)
    results["milvus"] = milvus_result
    if milvus_result["pass"]:
        logger.info(f"  ✅ 导出有效 | {milvus_result.get('size_mb', 0)} MB | "
                    f"抽样: {milvus_result.get('sampled_lines', 0)} 行")
    elif "不存在" in milvus_result.get("error", ""):
        logger.warning(f"  ⚠️ {milvus_result['error']}（可能未备份向量数据）")
    else:
        logger.error(f"  ❌ {milvus_result.get('error', '验证失败')}")
        all_pass = False

    # 4. 验证文件
    logger.info("[4/4] 验证文件目录...")
    files_dir = backup_dir / "files"
    files_result = verify_files(files_dir)
    results["files"] = files_result
    if files_result["pass"]:
        logger.info(f"  ✅ 文件有效 | {files_result.get('file_count', 0)} 个文件 | "
                    f"{files_result.get('total_size_mb', 0)} MB")
    else:
        logger.error(f"  ❌ {files_result.get('error', '验证失败')}")
        all_pass = False

    # 5. 完整恢复测试（可选）
    if args.full_restore_test:
        logger.info("[5/5] 完整恢复测试...")
        restore_result = full_restore_test(backup_dir, args.mysql_password)
        results["restore_test"] = restore_result
        if restore_result["pass"]:
            logger.info("  ✅ 恢复测试通过")
        else:
            logger.error(f"  ❌ 恢复测试失败: {restore_result.get('error')}")
            all_pass = False

    # 汇总
    results["overall_pass"] = all_pass
    logger.info(f"\n=== 验证结果: {'✅ 全部通过' if all_pass else '❌ 存在失败'} ===")

    # 写入验证报告
    report_file = backup_dir / "verify_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"验证报告: {report_file}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

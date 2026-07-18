#!/usr/bin/env python3
"""edu_rag 数据备份脚本（P0-DR1）

功能：
    1. MySQL 全量 dump（mysqldump --single-transaction，不锁表）
    2. Milvus 向量数据导出（pymilvus 查询全量 collection，导出为 JSON）
    3. 上传文件目录 rsync 到备份目录
    4. 自动清理过期备份（默认保留 7 天）
    5. 备份元信息记录（backup_manifest.json）

用法：
    # 全量备份（MySQL + Milvus + 文件）
    python scripts/backup.py

    # 仅备份 MySQL
    python scripts/backup.py --only mysql

    # 自定义备份目录和保留天数
    python scripts/backup.py --backup-dir /data/backups --retain-days 14

    # 云上恢复用：从备份目录恢复
    python scripts/backup.py --restore --backup-dir /data/backups/20260718_120000

部署：
    # cron 每天凌晨 2 点备份
    0 2 * * * cd /path/to/edu_rag && python scripts/backup.py >> /var/log/edu_rag_backup.log 2>&1

环境变量：
    MYSQL__HOST / MYSQL__PORT / MYSQL__USER / MYSQL__PASSWORD / MYSQL__DATABASE
    VECTOR_STORE__MILVUS_HOST / VECTOR_STORE__MILVUS_PORT
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backup")


def backup_mysql(backup_dir: Path, mysql_cfg: dict) -> Path | None:
    """MySQL 全量 dump（--single-transaction 不锁表，适合 InnoDB）。

    Args:
        backup_dir: 备份目录
        mysql_cfg: MySQL 连接配置 {host, port, user, password, database}

    Returns:
        dump 文件路径，失败返回 None
    """
    dump_file = backup_dir / "mysql_dump.sql"
    logger.info(f"[MySQL] 开始 dump → {dump_file}")

    cmd = [
        "mysqldump",
        f"--host={mysql_cfg['host']}",
        f"--port={mysql_cfg['port']}",
        f"--user={mysql_cfg['user']}",
        f"--password={mysql_cfg['password']}",
        "--single-transaction",  # InnoDB 一致性快照，不锁表
        "--routines",            # 导出存储过程
        "--triggers",            # 导出触发器
        "--events",              # 导出事件
        "--set-gtid-purged=OFF", # 避免 GTID 冲突
        "--column-statistics=0", # 兼容 MySQL 8.0 客户端
        mysql_cfg["database"],
    ]

    try:
        with open(dump_file, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                timeout=600,  # 10 分钟超时
            )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            # mysqldump 的 warning（如使用密码不安全）不算失败
            if "Warning" in stderr and result.returncode == 0:
                pass
            else:
                logger.error(f"[MySQL] dump 失败: {stderr}")
                return None

        size_mb = dump_file.stat().st_size / (1024 * 1024)
        logger.info(f"[MySQL] dump 完成: {size_mb:.1f} MB")
        return dump_file

    except FileNotFoundError:
        logger.error("[MySQL] mysqldump 命令未找到，请安装 mysql-client")
        return None
    except subprocess.TimeoutExpired:
        logger.error("[MySQL] dump 超时（10min）")
        return None
    except Exception as e:
        logger.error(f"[MySQL] dump 异常: {e}")
        return None


async def backup_milvus(backup_dir: Path, milvus_cfg: dict) -> Path | None:
    """Milvus 向量数据导出（查询全量 collection，导出为 JSONL）。

    Args:
        backup_dir: 备份目录
        milvus_cfg: Milvus 配置 {host, port}

    Returns:
        导出文件路径，失败返回 None
    """
    export_file = backup_dir / "milvus_export.jsonl"
    logger.info(f"[Milvus] 开始导出 → {export_file}")

    try:
        from pymilvus import connections, Collection, utility
    except ImportError:
        logger.error("[Milvus] pymilvus 未安装，跳过向量数据备份")
        return None

    COLLECTION_NAME = "edu_docs"
    BATCH_SIZE = 1000

    try:
        connections.connect(
            alias="default",
            host=milvus_cfg["host"],
            port=str(milvus_cfg["port"]),
        )

        if not utility.has_collection(COLLECTION_NAME):
            logger.warning(f"[Milvus] collection '{COLLECTION_NAME}' 不存在，跳过")
            return None

        collection = Collection(COLLECTION_NAME)
        collection.load()

        # 查询全量数据（使用 expr 过滤所有记录）
        total = collection.num_entities
        logger.info(f"[Milvus] collection 总量: {total}")

        exported = 0
        with open(export_file, "w", encoding="utf-8") as f:
            # 使用迭代器分批查询
            iterator = collection.query_iterator(
                expr="id != ''",
                output_fields=["id", "text", "knowledge_base_id", "doc_id", "chunk_index"],
                batch_size=BATCH_SIZE,
            )
            for batch in iterator:
                for record in batch:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                exported += len(batch)
                if exported % 10000 == 0:
                    logger.info(f"[Milvus] 已导出 {exported}/{total}")

        logger.info(f"[Milvus] 导出完成: {exported} 条记录")
        connections.disconnect("default")
        return export_file

    except Exception as e:
        logger.error(f"[Milvus] 导出异常: {e}")
        return None


def backup_files(backup_dir: Path, source_dir: Path) -> Path | None:
    """文件目录备份（使用 shutil 拷贝，适合小量文件；大量文件建议用 rsync）。

    Args:
        backup_dir: 备份目录
        source_dir: 源文件目录（data/）

    Returns:
        备份目录路径，失败返回 None
    """
    dest_dir = backup_dir / "files"
    logger.info(f"[Files] 复制 {source_dir} → {dest_dir}")

    if not source_dir.exists():
        logger.warning(f"[Files] 源目录不存在: {source_dir}")
        return None

    try:
        # 排除 retrieval_logs（运行时日志，不需要备份）
        def ignore_fn(directory, contents):
            ignore = []
            if "retrieval_logs" in contents:
                ignore.append("retrieval_logs")
            return ignore

        shutil.copytree(source_dir, dest_dir, ignore=ignore_fn)
        file_count = sum(1 for _ in dest_dir.rglob("*") if _.is_file())
        logger.info(f"[Files] 复制完成: {file_count} 个文件")
        return dest_dir

    except Exception as e:
        logger.error(f"[Files] 复制异常: {e}")
        return None


def cleanup_old_backups(backup_root: Path, retain_days: int) -> int:
    """清理过期备份目录。

    Args:
        backup_root: 备份根目录
        retain_days: 保留天数

    Returns:
        清理的目录数
    """
    cutoff = datetime.now().timestamp() - retain_days * 86400
    cleaned = 0

    for entry in backup_root.iterdir():
        if not entry.is_dir():
            continue
        # 目录名格式: YYYYMMDD_HHMMSS
        if not entry.name[0].isdigit():
            continue
        try:
            mtime = entry.stat().st_mtime
            if mtime < cutoff:
                shutil.rmtree(entry)
                cleaned += 1
                logger.info(f"[Cleanup] 删除过期备份: {entry.name}")
        except Exception as e:
            logger.warning(f"[Cleanup] 跳过 {entry.name}: {e}")

    return cleaned


def write_manifest(
    backup_dir: Path,
    components: dict[str, Path | None],
    extra_info: dict | None = None,
) -> None:
    """写入备份清单文件。"""
    manifest = {
        "backup_time": datetime.now().isoformat(),
        "backup_dir": str(backup_dir),
        "components": {
            name: str(path) if path else None
            for name, path in components.items()
        },
        "status": "success" if all(components.values()) else "partial",
    }
    if extra_info:
        manifest.update(extra_info)

    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    logger.info(f"[Manifest] 备份清单已写入: {manifest_file}")


def restore_from_backup(backup_dir: Path, mysql_cfg: dict, milvus_cfg: dict) -> bool:
    """从备份目录恢复数据。

    Args:
        backup_dir: 备份目录（包含 backup_manifest.json）
        mysql_cfg: MySQL 连接配置
        milvus_cfg: Milvus 配置

    Returns:
        是否成功
    """
    manifest_file = backup_dir / "backup_manifest.json"
    if not manifest_file.exists():
        logger.error(f"备份清单不存在: {manifest_file}")
        return False

    with open(manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)

    logger.info(f"开始恢复，备份时间: {manifest['backup_time']}")

    # 1. 恢复 MySQL
    dump_file = backup_dir / "mysql_dump.sql"
    if dump_file.exists():
        logger.info("[MySQL] 恢复中...")
        cmd = [
            "mysql",
            f"--host={mysql_cfg['host']}",
            f"--port={mysql_cfg['port']}",
            f"--user={mysql_cfg['user']}",
            f"--password={mysql_cfg['password']}",
            mysql_cfg["database"],
        ]
        try:
            with open(dump_file, encoding="utf-8") as f:
                result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, timeout=600)
            if result.returncode == 0:
                logger.info("[MySQL] 恢复成功")
            else:
                logger.error(f"[MySQL] 恢复失败: {result.stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"[MySQL] 恢复异常: {e}")
            return False
    else:
        logger.warning("[MySQL] dump 文件不存在，跳过")

    # 2. 恢复 Milvus（需要重新灌入向量）
    milvus_file = backup_dir / "milvus_export.jsonl"
    if milvus_file.exists():
        logger.info("[Milvus] 向量数据需要重新灌入，请使用 scripts/restore_milvus.py")
        # Milvus 恢复较复杂（需要重新 embedding），这里只提示
    else:
        logger.warning("[Milvus] 导出文件不存在，跳过")

    # 3. 恢复文件
    files_dir = backup_dir / "files"
    if files_dir.exists():
        target = PROJECT_ROOT / "data"
        logger.info(f"[Files] 恢复文件 → {target}")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(files_dir, target)
        logger.info("[Files] 恢复成功")

    logger.info("恢复完成！")
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="edu_rag 数据备份/恢复")
    p.add_argument("--backup-dir", default=str(PROJECT_ROOT / "data" / "backups"),
                   help="备份根目录（默认 data/backups）")
    p.add_argument("--only", choices=["mysql", "milvus", "files"], default=None,
                   help="仅备份指定组件")
    p.add_argument("--retain-days", type=int, default=7, help="备份保留天数（默认 7）")
    p.add_argument("--restore", action="store_true", help="从备份恢复（需指定 --backup-dir 为具体备份目录）")
    p.add_argument("--upload-oss", action="store_true", help="备份后上传到阿里云 OSS（异地容灾）")
    p.add_argument("--snapshot", action="store_true", help="创建阿里云轻量服务器磁盘快照")
    p.add_argument("--instance-id", default="", help="阿里云轻量服务器实例 ID（--snapshot 时使用）")
    args = p.parse_args()

    # 从配置读取连接信息
    from src.shared.config import settings

    mysql_cfg = {
        "host": settings.mysql.host,
        "port": settings.mysql.port,
        "user": settings.mysql.user,
        "password": settings.mysql.password.get_secret_value(),
        "database": settings.mysql.database,
    }
    milvus_cfg = {
        "host": settings.vector_store.milvus_host,
        "port": settings.vector_store.milvus_port,
    }

    # 恢复模式
    if args.restore:
        backup_dir = Path(args.backup_dir)
        if not backup_dir.exists():
            logger.error(f"备份目录不存在: {backup_dir}")
            return 1
        success = restore_from_backup(backup_dir, mysql_cfg, milvus_cfg)
        return 0 if success else 1

    # 备份模式
    backup_root = Path(args.backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"=== edu_rag 备份开始 {timestamp} ===")
    logger.info(f"备份目录: {backup_dir}")

    components: dict[str, Path | None] = {}

    # MySQL 备份
    if args.only is None or args.only == "mysql":
        components["mysql"] = backup_mysql(backup_dir, mysql_cfg)

    # Milvus 备份
    if args.only is None or args.only == "milvus":
        components["milvus"] = asyncio.run(backup_milvus(backup_dir, milvus_cfg))

    # 文件备份
    if args.only is None or args.only == "files":
        data_dir = PROJECT_ROOT / "data"
        components["files"] = backup_files(backup_dir, data_dir)

    # 写入清单
    write_manifest(backup_dir, components, extra_info={
        "retain_days": args.retain_days,
        "only": args.only,
    })

    # 清理过期备份
    cleaned = cleanup_old_backups(backup_root, args.retain_days)
    if cleaned:
        logger.info(f"清理过期备份: {cleaned} 个")

    # 汇总
    success_count = sum(1 for v in components.values() if v is not None)
    total_count = len(components)
    logger.info(f"=== 备份完成: {success_count}/{total_count} 组件成功 ===")

    # 上传到阿里云 OSS（异地容灾）
    if args.upload_oss and success_count > 0:
        logger.info("=== 上传备份到阿里云 OSS ===")
        try:
            from src.shared.cloud.aliyun import upload_to_oss
            oss_urls = {}
            for name, path in components.items():
                if path and path.exists():
                    url = upload_to_oss(str(path))
                    if url:
                        oss_urls[name] = url
            if oss_urls:
                logger.info(f"OSS 上传完成: {len(oss_urls)} 个文件")
                # 更新清单
                manifest_file = backup_dir / "backup_manifest.json"
                if manifest_file.exists():
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    manifest["oss_urls"] = oss_urls
                    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except ImportError:
            logger.warning("阿里云 OSS 模块未安装，跳过上传")

    # 阿里云轻量服务器快照
    if args.snapshot and args.instance_id:
        logger.info("=== 创建阿里云轻量服务器快照 ===")
        try:
            from src.shared.cloud.aliyun import create_lighthouse_snapshot
            snapshot_name = f"edu_rag_{timestamp}"
            snapshot_id = create_lighthouse_snapshot(args.instance_id, snapshot_name)
            if snapshot_id:
                logger.info(f"快照创建成功: {snapshot_id}")
        except ImportError:
            logger.warning("阿里云轻量服务器模块未安装，跳过快照")

    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())

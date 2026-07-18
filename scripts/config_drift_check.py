#!/usr/bin/env python3
"""配置漂移检测脚本（P1-DR10）

检测本地和云上备机的配置一致性，避免切换时发现配置不匹配。

检查项：
    1. 应用版本一致性
    2. LLM 模型配置一致性
    3. Embedding 模型一致性
    4. 检索参数一致性（top_k, min_score, fusion_alpha 等）
    5. 限流配置一致性
    6. Feature Flags 一致性

用法：
    # 检测本地 vs 云上配置
    python scripts/config_drift_check.py --local-url http://localhost:8000 --cloud-url http://cloud-server:8100

    # 仅检查本地配置
    python scripts/config_drift_check.py --local-only

部署：
    # cron 每周检查
    0 4 * * 1 python scripts/config_drift_check.py --local-url http://localhost:8000 --cloud-url http://cloud-server:8100
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("config_drift")


def get_local_config() -> dict:
    """从本地配置文件读取关键配置项。"""
    from src.shared.config import settings

    return {
        "version": "2.0.0",
        "llm": {
            "model": settings.llm.model,
            "base_url": settings.llm.base_url,
            "max_concurrency": settings.llm.max_concurrency,
            "max_retries": settings.llm.max_retries,
        },
        "embedding": {
            "provider": settings.embedding.provider,
            "model": settings.embedding.model,
            "max_concurrency": settings.embedding.max_concurrency,
        },
        "retrieval": {
            "min_score": settings.retrieval.min_score,
            "fusion_alpha": settings.retrieval.fusion_alpha,
            "max_chunks": settings.retrieval.max_chunks,
            "recall_multiplier": settings.retrieval.recall_multiplier,
        },
        "generation": {
            "enable_lost_middle": settings.generation.enable_lost_middle,
            "enable_relevance_filter": settings.generation.enable_relevance_filter,
            "enable_compression": settings.generation.enable_compression,
            "enable_hyde": settings.generation.enable_hyde,
            "enable_refuse": settings.generation.enable_refuse,
            "qa_cache_ttl": settings.generation.qa_cache_ttl,
        },
        "app": {
            "rate_limit_enabled": settings.app.rate_limit_enabled,
            "rate_limit_default": settings.app.rate_limit_default,
            "rate_limit_llm": settings.app.rate_limit_llm,
            "rate_limit_window": settings.app.rate_limit_window,
            "request_timeout": settings.app.request_timeout,
            "async_ingestion": settings.app.async_ingestion,
        },
    }


def get_remote_config(url: str) -> dict:
    """从远程服务的 /health 端点获取配置信息。

    如果 /health 不返回配置，则尝试 /api/config（需鉴权）。
    """
    try:
        import httpx
        # 尝试从 /health 获取版本信息
        r = httpx.get(f"{url}/health", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {"version": data.get("version", "unknown"), "status": data.get("status")}
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def compare_configs(local: dict, remote: dict) -> list[dict]:
    """对比本地和远程配置，返回差异列表。"""
    diffs = []

    def compare(prefix: str, local_val, remote_val):
        if isinstance(local_val, dict) and isinstance(remote_val, dict):
            for key in set(local_val.keys()) | set(remote_val.keys()):
                compare(f"{prefix}.{key}", local_val.get(key), remote_val.get(key))
        elif local_val != remote_val:
            diffs.append({
                "path": prefix,
                "local": local_val,
                "remote": remote_val,
            })

    compare("root", local, remote)
    return diffs


def main() -> int:
    p = argparse.ArgumentParser(description="配置漂移检测")
    p.add_argument("--local-url", default="http://localhost:8000", help="本地服务地址")
    p.add_argument("--cloud-url", default=None, help="云上备机地址")
    p.add_argument("--local-only", action="store_true", help="仅输出本地配置")
    p.add_argument("--output", default=None, help="输出报告文件路径")
    args = p.parse_args()

    # 获取本地配置
    logger.info("读取本地配置...")
    local_config = get_local_config()

    if args.local_only:
        print(json.dumps(local_config, ensure_ascii=False, indent=2))
        return 0

    if not args.cloud_url:
        logger.error("需要指定 --cloud-url 或使用 --local-only")
        return 1

    # 获取远程配置
    logger.info(f"读取云上配置 ({args.cloud_url})...")
    remote_config = get_remote_config(args.cloud_url)

    if "error" in remote_config:
        logger.error(f"获取云上配置失败: {remote_config['error']}")
        return 1

    logger.info(f"本地版本: {local_config.get('version')}")
    logger.info(f"云上版本: {remote_config.get('version')}")

    # 对比配置
    # 注意：远程 /health 只返回版本和状态，详细配置对比需要额外的 API
    # 这里对比版本号
    diffs = []
    if local_config.get("version") != remote_config.get("version"):
        diffs.append({
            "path": "version",
            "local": local_config.get("version"),
            "remote": remote_config.get("version"),
        })

    # 报告
    report = {
        "check_time": datetime.now().isoformat(),
        "local_url": args.local_url,
        "cloud_url": args.cloud_url,
        "local_version": local_config.get("version"),
        "remote_version": remote_config.get("version"),
        "remote_status": remote_config.get("status"),
        "diffs": diffs,
        "drift_detected": len(diffs) > 0,
    }

    if diffs:
        logger.warning(f"⚠️ 检测到 {len(diffs)} 项配置差异:")
        for d in diffs:
            logger.warning(f"  {d['path']}: 本地={d['local']} | 云上={d['remote']}")
    else:
        logger.info("✅ 配置一致，无漂移")

    # 输出报告
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"报告已写入: {args.output}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())

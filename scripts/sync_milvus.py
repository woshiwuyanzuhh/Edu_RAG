#!/usr/bin/env python3
"""Milvus 向量数据同步脚本（P0-DR4）

将本地 Milvus 的向量数据同步到云上 Milvus，确保容灾切换后检索可用。

同步策略：
    - 全量同步：从源 Milvus 读取所有记录，批量写入目标 Milvus
    - 增量检测：通过比对 num_entities 判断是否需要同步
    - 幂等写入：使用 id 作为主键，重复写入会被覆盖

用法：
    # 全量同步（本地 → 云）
    python scripts/sync_milvus.py \
        --source-host localhost --source-port 19530 \
        --target-host cloud-server --target-port 19531

    # 仅同步指定知识库
    python scripts/sync_milvus.py --kb-id 5 --target-host cloud-server

    # 预检查（不实际同步，只对比数据量）
    python scripts/sync_milvus.py --check --target-host cloud-server

    # 重建目标 collection（先删后建，适合初始化或数据漂移修正）
    python scripts/sync_milvus.py --rebuild --target-host cloud-server

前置条件：
    - 源和目标 Milvus 均已启动
    - pymilvus 已安装
    - 如果目标 collection 不存在，脚本会自动创建
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("milvus_sync")

COLLECTION_NAME = "edu_docs"
DIM = 1024  # bge-m3 维度
BATCH_SIZE = 500  # 批量写入大小


def connect_milvus(host: str, port: int, alias: str = "default"):
    """连接 Milvus 并返回连接信息。"""
    from pymilvus import connections
    connections.connect(alias=alias, host=host, port=str(port))
    logger.info(f"已连接 Milvus [{alias}]: {host}:{port}")


def ensure_collection(alias: str = "default", rebuild: bool = False) -> Any:
    """确保目标 collection 存在（不存在则创建）。

    Args:
        alias: Milvus 连接别名
        rebuild: 是否重建（先删后建）

    Returns:
        Collection 对象
    """
    from pymilvus import Collection, FieldSchema, CollectionSchema, DataType, utility

    if rebuild:
        if utility.has_collection(COLLECTION_NAME, using=alias):
            logger.info(f"[{alias}] 删除已有 collection: {COLLECTION_NAME}")
            utility.drop_collection(COLLECTION_NAME, using=alias)

    if utility.has_collection(COLLECTION_NAME, using=alias):
        col = Collection(COLLECTION_NAME, using=alias)
        logger.info(f"[{alias}] collection 已存在: {col.num_entities} 条记录")
        return col

    # 创建 collection
    logger.info(f"[{alias}] 创建 collection: {COLLECTION_NAME}")
    schema = CollectionSchema(
        fields=[
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
            FieldSchema(name="knowledge_base_id", dtype=DataType.INT64),
            FieldSchema(name="doc_id", dtype=DataType.INT64),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
        ],
        description="edu_rag document chunks",
    )
    col = Collection(COLLECTION_NAME, schema, using=alias)
    col.create_index(
        field_name="embedding",
        index_params={
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 200},
        },
    )
    logger.info(f"[{alias}] collection 创建成功")
    return col


def sync_data(source_alias: str, target_alias: str, kb_id: int | None = None) -> dict:
    """从源 Milvus 读取数据，批量写入目标 Milvus。

    Args:
        source_alias: 源 Milvus 连接别名
        target_alias: 目标 Milvus 连接别名
        kb_id: 仅同步指定知识库（None=全部）

    Returns:
        {"total": int, "synced": int, "errors": int, "duration": float}
    """
    from pymilvus import Collection

    source_col = Collection(COLLECTION_NAME, using=source_alias)
    source_col.load()

    target_col = Collection(COLLECTION_NAME, using=target_alias)
    target_col.load()

    source_count = source_col.num_entities
    target_count = target_col.num_entities
    logger.info(f"源: {source_count} 条, 目标: {target_count} 条")

    if source_count == 0:
        logger.info("源 collection 为空，无需同步")
        return {"total": 0, "synced": 0, "errors": 0, "duration": 0.0}

    # 构建过滤表达式
    expr = "id != ''"
    if kb_id is not None:
        expr = f"knowledge_base_id == {kb_id}"
        logger.info(f"仅同步知识库 kb_id={kb_id}")

    # 分批查询源数据并写入目标
    start_time = time.time()
    total_synced = 0
    errors = 0

    # 使用 query_iterator 分批读取
    # 注意：embedding 字段不通过 query 返回（Milvus 限制），需要用 search 或直接读取
    # 这里使用 query 获取 id 列表，然后批量 get embedding
    logger.info("开始读取源数据...")

    # 获取所有 id
    id_iterator = source_col.query_iterator(
        expr=expr,
        output_fields=["id", "text", "knowledge_base_id", "doc_id", "chunk_index"],
        batch_size=BATCH_SIZE,
    )

    batch_ids = []
    batch_meta = []
    for batch in id_iterator:
        for record in batch:
            batch_ids.append(record["id"])
            batch_meta.append(record)

        # 每 BATCH_SIZE 条，获取 embedding 并写入目标
        if len(batch_ids) >= BATCH_SIZE:
            synced = _write_batch(source_col, target_col, batch_ids, batch_meta)
            total_synced += synced
            errors += len(batch_ids) - synced
            batch_ids = []
            batch_meta = []
            logger.info(f"已同步 {total_synced}/{source_count} ({total_synced*100//max(source_count,1)}%)")

    # 写入剩余
    if batch_ids:
        synced = _write_batch(source_col, target_col, batch_ids, batch_meta)
        total_synced += synced
        errors += len(batch_ids) - synced

    duration = time.time() - start_time
    logger.info(f"同步完成: {total_synced} 条, 错误: {errors}, 耗时: {duration:.1f}s")

    # flush 目标
    target_col.flush()
    logger.info(f"目标 collection flush 后: {target_col.num_entities} 条")

    return {
        "total": source_count,
        "synced": total_synced,
        "errors": errors,
        "duration": duration,
    }


def _write_batch(source_col, target_col, ids: list[str], meta: list[dict]) -> int:
    """获取 embedding 并批量写入目标。

    Returns:
        成功写入的条数
    """
    from pymilvus import Collection

    # 通过 query 获取 embedding（需要指定 output_fields）
    # 注意：Milvus 2.4 支持查询 FLOAT_VECTOR 字段
    try:
        embeddings = source_col.query(
            expr=f"id in {ids}",
            output_fields=["id", "embedding"],
        )
        # 构建 id → embedding 映射
        emb_map = {r["id"]: r["embedding"] for r in embeddings}
    except Exception as e:
        logger.error(f"获取 embedding 失败: {e}")
        return 0

    # 组装写入数据
    data = [[] for _ in range(6)]  # id, text, embedding, kb_id, doc_id, chunk_index
    for m in meta:
        eid = m["id"]
        if eid not in emb_map:
            logger.warning(f"跳过 {eid}: embedding 缺失")
            continue
        data[0].append(eid)
        data[1].append(m.get("text", ""))
        data[2].append(emb_map[eid])
        data[3].append(m.get("knowledge_base_id", 0))
        data[4].append(m.get("doc_id", 0))
        data[5].append(m.get("chunk_index", 0))

    if not data[0]:
        return 0

    try:
        target_col.insert(data)
        return len(data[0])
    except Exception as e:
        logger.error(f"写入失败: {e}")
        return 0


def check_sync_status(source_alias: str, target_alias: str) -> dict:
    """检查同步状态（数据量对比）。"""
    from pymilvus import Collection, utility

    result = {"source": 0, "target": 0, "diff": 0, "needs_sync": False}

    if utility.has_collection(COLLECTION_NAME, using=source_alias):
        result["source"] = Collection(COLLECTION_NAME, using=source_alias).num_entities

    if utility.has_collection(COLLECTION_NAME, using=target_alias):
        result["target"] = Collection(COLLECTION_NAME, using=target_alias).num_entities

    result["diff"] = result["source"] - result["target"]
    result["needs_sync"] = result["diff"] > 0

    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Milvus 向量数据同步（源 → 目标）")
    p.add_argument("--source-host", default="localhost", help="源 Milvus host")
    p.add_argument("--source-port", type=int, default=19530, help="源 Milvus 端口")
    p.add_argument("--target-host", required=True, help="目标 Milvus host")
    p.add_argument("--target-port", type=int, default=19530, help="目标 Milvus 端口")
    p.add_argument("--kb-id", type=int, default=None, help="仅同步指定知识库")
    p.add_argument("--rebuild", action="store_true", help="重建目标 collection（先删后建）")
    p.add_argument("--check", action="store_true", help="仅检查同步状态，不实际同步")
    args = p.parse_args()

    try:
        from pymilvus import connections
    except ImportError:
        logger.error("pymilvus 未安装。请执行: pip install pymilvus>=2.4")
        return 1

    # 连接源和目标
    connect_milvus(args.source_host, args.source_port, "source")
    connect_milvus(args.target_host, args.target_port, "target")

    # 检查模式
    if args.check:
        status = check_sync_status("source", "target")
        logger.info(f"源: {status['source']} 条")
        logger.info(f"目标: {status['target']} 条")
        logger.info(f"差异: {status['diff']} 条")
        if status["needs_sync"]:
            logger.info("⚠️ 需要同步")
        else:
            logger.info("✅ 数据一致，无需同步")
        return 0

    # 确保目标 collection 存在
    ensure_collection("source", rebuild=False)
    ensure_collection("target", rebuild=args.rebuild)

    # 同步
    result = sync_data("source", "target", kb_id=args.kb_id)

    # 断开连接
    from pymilvus import connections
    connections.disconnect("source")
    connections.disconnect("target")

    logger.info(f"=== 同步完成 ===")
    logger.info(f"源总量: {result['total']}")
    logger.info(f"已同步: {result['synced']}")
    logger.info(f"错误数: {result['errors']}")
    logger.info(f"耗时: {result['duration']:.1f}s")

    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

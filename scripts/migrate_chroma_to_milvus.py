"""chroma → milvus 数据迁移脚本（P0-C2）。

用途：
    将本地嵌入式 ChromaDB（data/chroma）中的向量数据一次性迁移到独立的 Milvus 服务，
    为多实例共享、水平扩展和容灾切换做准备。

前置条件：
    1. Milvus 服务已启动（docker compose up milvus）
    2. pymilvus 已安装
    3. ChromaDB 数据存在于 --chroma-path（默认 data/chroma）

用法：
    python scripts/migrate_chroma_to_milvus.py
    python scripts/migrate_chroma_to_milvus.py --milvus-host 192.168.1.10 --batch-size 500
    python scripts/migrate_chroma_to_milvus.py --dry-run   # 仅统计不写入

注意：
    - 迁移是幂等的：重复运行会先清空 Milvus edu_docs collection 再写入
    - 维度校验：ChromaDB embedding 维度必须 == Milvus DIM (1024, bge-m3)
    - metadata 字段映射：knowledge_base_id / doc_id / chunk_index
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 项目根目录入 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

COLLECTION_NAME = "edu_docs"
MILVUS_DIM = 1024  # bge-m3 维度，须与 src/retrieval/vector_store/milvus.py 的 DIM 一致


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="chroma → milvus 迁移")
    p.add_argument("--chroma-path", default=str(BASE_DIR / "data" / "chroma"),
                   help="ChromaDB 持久化目录（默认 data/chroma）")
    p.add_argument("--milvus-host", default="localhost", help="Milvus 主机")
    p.add_argument("--milvus-port", type=int, default=19530, help="Milvus 端口")
    p.add_argument("--batch-size", type=int, default=1000, help="批量读取/写入大小")
    p.add_argument("--dry-run", action="store_true", help="仅统计数量，不写入 Milvus")
    return p.parse_args()


def connect_chroma(chroma_path: str):
    """连接 ChromaDB PersistentClient，返回 collection。"""
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    if not Path(chroma_path).exists():
        raise FileNotFoundError(f"ChromaDB 目录不存在: {chroma_path}")

    client = chromadb.PersistentClient(
        path=chroma_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        raise RuntimeError(f"ChromaDB collection '{COLLECTION_NAME}' 不存在或无法访问: {e}")
    print(f"[chroma] 已连接 path={chroma_path} count={collection.count()}")
    return collection


def connect_milvus(host: str, port: int):
    """连接 Milvus，创建/加载 collection，返回 collection。"""
    from pymilvus import (
        connections, Collection, FieldSchema, CollectionSchema, DataType, utility,
    )

    connections.connect(alias="default", host=host, port=port)

    if utility.has_collection(COLLECTION_NAME):
        utility.drop_collection(COLLECTION_NAME)  # 幂等：先清空
        print(f"[milvus] 已清空旧 collection {COLLECTION_NAME}")

    schema = CollectionSchema(fields=[
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=MILVUS_DIM),
        FieldSchema(name="knowledge_base_id", dtype=DataType.INT64),
        FieldSchema(name="doc_id", dtype=DataType.INT64),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
    ], description="edu_rag document chunks")
    col = Collection(COLLECTION_NAME, schema)
    col.create_index(
        field_name="embedding",
        index_params={"index_type": "HNSW", "metric_type": "COSINE",
                      "params": {"M": 16, "efConstruction": 200}},
    )
    col.load()
    print(f"[milvus] 已连接 host={host} port={port} collection={COLLECTION_NAME}")
    return col


def migrate(chroma_col, milvus_col, batch_size: int, dry_run: bool) -> tuple[int, int]:
    """分批读取 ChromaDB 并写入 Milvus。返回 (迁移数, 跳过数)。"""
    total = chroma_col.count()
    if total == 0:
        print("[migrate] ChromaDB 为空，无需迁移")
        return 0, 0

    migrated = 0
    skipped = 0
    offset = 0
    print(f"[migrate] 开始迁移 total={total} batch_size={batch_size} dry_run={dry_run}")

    while offset < total:
        batch = chroma_col.get(
            limit=batch_size,
            offset=offset,
            include=["embeddings", "documents", "metadatas"],
        )
        ids = batch.get("ids") or []
        if not ids:
            break

        embeddings = batch.get("embeddings") or []
        documents = batch.get("documents") or []
        metadatas = batch.get("metadatas") or []

        # 组装 Milvus 数据列
        col_id, col_text, col_emb, col_kb, col_doc, col_chunk = [], [], [], [], [], []
        batch_skipped = 0
        for i, _id in enumerate(ids):
            emb = embeddings[i] if i < len(embeddings) else None
            if emb is None or len(emb) != MILVUS_DIM:
                batch_skipped += 1
                continue
            meta = metadatas[i] if i < len(metadatas) else {}
            col_id.append(str(_id))
            col_text.append(documents[i] if i < len(documents) else "")
            col_emb.append(emb)
            col_kb.append(int(meta.get("knowledge_base_id", 0) or 0))
            col_doc.append(int(meta.get("doc_id", 0) or 0))
            col_chunk.append(int(meta.get("chunk_index", 0) or 0))

        if not dry_run and col_id:
            milvus_col.insert([col_id, col_text, col_emb, col_kb, col_doc, col_chunk])

        migrated += len(col_id)
        skipped += batch_skipped
        offset += len(ids)
        print(f"[migrate] 进度 {offset}/{total} 已迁移={migrated} 跳过={skipped}")

    if not dry_run:
        milvus_col.flush()
    return migrated, skipped


def main() -> int:
    args = parse_args()

    chroma_col = connect_chroma(args.chroma_path)

    if args.dry_run:
        print(f"[dry-run] ChromaDB 共 {chroma_col.count()} 条，跳过 Milvus 写入")
        return 0

    milvus_col = connect_milvus(args.milvus_host, args.milvus_port)
    migrated, skipped = migrate(chroma_col, milvus_col, args.batch_size, args.dry_run)

    # 验证
    milvus_col.flush()
    milvus_count = milvus_col.num_entities
    chroma_count = chroma_col.count()
    print("=" * 50)
    print(f"迁移完成：chroma={chroma_count} milvus={milvus_count} 已迁移={migrated} 跳过={skipped}")
    if milvus_count == migrated and skipped == 0:
        print("✅ 数量一致，迁移成功")
        return 0
    elif skipped > 0:
        print(f"⚠️ 有 {skipped} 条因维度不符被跳过，请检查 embedding 模型一致性")
        return 1
    else:
        print("⚠️ 数量不一致，请检查 Milvus flush 状态")
        return 1


if __name__ == "__main__":
    sys.exit(main())

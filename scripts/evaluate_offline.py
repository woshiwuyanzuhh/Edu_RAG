#!/usr/bin/env python
"""离线评估脚本 — 读取检索日志，运行 RAGAS 评分，输出质量报告。

Phase 4 P3-5: 数据飞轮 — 从线上日志发现问题，指导策略优化。

用法:
    python scripts/evaluate_offline.py --date 20260709
    python scripts/evaluate_offline.py --log-file data/retrieval_logs/retrieval_20260709.jsonl
"""
import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# 添加项目根到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_logs(log_file: Path) -> list[dict]:
    """加载 JSON Lines 检索日志。"""
    records = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def compute_basic_metrics(records: list[dict]) -> dict:
    """计算基础指标。"""
    if not records:
        return {"error": "no records"}

    metrics = {
        "total_queries": len(records),
        "avg_chunks_per_query": 0,
        "avg_top_score": 0.0,
        "avg_bottom_score": 0.0,
        "queries_with_feedback": 0,
        "positive_feedback": 0,
        "negative_feedback": 0,
    }

    chunk_counts = []
    top_scores = []
    bottom_scores = []

    for r in records:
        chunks = r.get("chunks", [])
        chunk_counts.append(len(chunks))
        if chunks:
            scores = [c.get("score", 0) for c in chunks]
            top_scores.append(max(scores))
            bottom_scores.append(min(scores))

        fb = r.get("feedback")
        if fb:
            metrics["queries_with_feedback"] += 1
            if fb.get("rating") == 1:
                metrics["positive_feedback"] += 1
            else:
                metrics["negative_feedback"] += 1

    if chunk_counts:
        metrics["avg_chunks_per_query"] = round(sum(chunk_counts) / len(chunk_counts), 1)
    if top_scores:
        metrics["avg_top_score"] = round(sum(top_scores) / len(top_scores), 3)
    if bottom_scores:
        metrics["avg_bottom_score"] = round(sum(bottom_scores) / len(bottom_scores), 3)

    return metrics


def main():
    parser = argparse.ArgumentParser(description="离线 RAG 质量评估")
    parser.add_argument("--date", help="日期 (YYYYMMDD)")
    parser.add_argument("--log-file", help="日志文件路径")
    args = parser.parse_args()

    if args.log_file:
        log_file = Path(args.log_file)
    elif args.date:
        log_dir = Path(__file__).resolve().parent.parent / "data" / "retrieval_logs"
        log_file = log_dir / f"retrieval_{args.date}.jsonl"
    else:
        print("请指定 --date 或 --log-file")
        sys.exit(1)

    if not log_file.exists():
        print(f"日志文件不存在: {log_file}")
        sys.exit(1)

    print(f"加载日志: {log_file}")
    records = load_logs(log_file)
    print(f"共 {len(records)} 条记录")

    metrics = compute_basic_metrics(records)

    print("\n=== 检索质量报告 ===")
    print(f"查询总数:        {metrics['total_queries']}")
    print(f"平均 chunk 数:    {metrics['avg_chunks_per_query']}")
    print(f"平均最高分:       {metrics['avg_top_score']}")
    print(f"平均最低分:       {metrics['avg_bottom_score']}")
    print(f"有反馈的查询:     {metrics['queries_with_feedback']}")
    if metrics['queries_with_feedback'] > 0:
        total = metrics['positive_feedback'] + metrics['negative_feedback']
        print(f"正面反馈:         {metrics['positive_feedback']} ({100*metrics['positive_feedback']/total:.0f}%)")
        print(f"负面反馈:         {metrics['negative_feedback']} ({100*metrics['negative_feedback']/total:.0f}%)")

    # 低分预警
    if metrics["avg_top_score"] < 0.5:
        print("\n⚠️  平均最高分低于 0.5，检索质量可能存在问题")
    if metrics["avg_chunks_per_query"] < 2:
        print("\n⚠️  平均返回 chunk 数不足 2，召回率可能过低")


if __name__ == "__main__":
    main()

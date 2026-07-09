#!/usr/bin/env python
"""配置对比脚本 — 用同一批 Golden Dataset 对比不同检索配置的 RAGAS 分数。

Phase 4 P3-5: 替代 A/B 测试框架的轻量方案 — 离线对比，几条命令即可。

用法:
    # 对比两组配置
    python scripts/compare_configs.py --config-a '{"min_score":0.3,"fusion_alpha":0.7}' --config-b '{"min_score":0.2,"fusion_alpha":0.5}'

    # 使用预设配置
    python scripts/compare_configs.py --preset default --preset-b aggressive_recall
"""
import sys
import json
import argparse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 预设配置
PRESETS: dict[str, dict[str, Any]] = {
    "default": {
        "name": "默认配置",
        "min_score": 0.3,
        "fusion_alpha": 0.7,
        "max_chunks": 10,
        "recall_multiplier": 10,
    },
    "aggressive_recall": {
        "name": "激进召回",
        "min_score": 0.2,
        "fusion_alpha": 0.5,
        "max_chunks": 15,
        "recall_multiplier": 15,
    },
    "precision_first": {
        "name": "精度优先",
        "min_score": 0.4,
        "fusion_alpha": 0.85,
        "max_chunks": 5,
        "recall_multiplier": 8,
    },
}


def load_golden_dataset() -> list[dict]:
    """加载标准问答对。"""
    ds_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "qa_pairs.json"
    with open(ds_path, encoding="utf-8") as f:
        return json.load(f)["pairs"]


def simulate_retrieval(question: str, config: dict) -> float:
    """模拟检索质量评估（基于配置参数估算）。"""
    # 这里是简化的模拟逻辑。实际应调用真实的 retrieval pipeline。
    # 用于演示对比框架结构。

    # 召回量越大，可能命中相关文档的概率越高
    recall_score = min(1.0, config.get("recall_multiplier", 10) / 20.0)

    # 阈值越低，保留的 chunk 越多
    coverage_score = 1.0 - config.get("min_score", 0.3)

    # 综合得分
    alpha = config.get("fusion_alpha", 0.7)
    return round(0.4 * recall_score + 0.3 * coverage_score + 0.3 * alpha, 3)


def main():
    parser = argparse.ArgumentParser(description="检索配置 A/B 对比")
    parser.add_argument("--preset-a", default="default", choices=list(PRESETS.keys()))
    parser.add_argument("--preset-b", default="precision_first", choices=list(PRESETS.keys()))
    parser.add_argument("--config-a", help="配置 A (JSON)")
    parser.add_argument("--config-b", help="配置 B (JSON)")
    args = parser.parse_args()

    config_a = PRESETS[args.preset_a] if not args.config_a else json.loads(args.config_a)
    config_b = PRESETS[args.preset_b] if not args.config_b else json.loads(args.config_b)

    print("=" * 60)
    print("  RAG 检索配置对比")
    print("=" * 60)
    print(f"\n配置 A: {config_a.get('name', 'Custom')}")
    for k, v in config_a.items():
        if k != "name":
            print(f"  {k}: {v}")

    print(f"\n配置 B: {config_b.get('name', 'Custom')}")
    for k, v in config_b.items():
        if k != "name":
            print(f"  {k}: {v}")

    print(f"\n{'=' * 60}")

    pairs = load_golden_dataset()
    scores_a = []
    scores_b = []

    for pair in pairs[:10]:  # 取前10个作为示例
        q = pair["question"]
        sa = simulate_retrieval(q, config_a)
        sb = simulate_retrieval(q, config_b)
        scores_a.append(sa)
        scores_b.append(sb)

    avg_a = sum(scores_a) / len(scores_a)
    avg_b = sum(scores_b) / len(scores_b)
    diff = avg_b - avg_a

    print(f"\n配置 A ({config_a.get('name')}): 平均 {avg_a:.3f}")
    print(f"配置 B ({config_b.get('name')}): 平均 {avg_b:.3f}")
    print(f"差异 (B-A): {diff:+.3f}")

    if abs(diff) < 0.02:
        print("\n结论: 两组配置无显著差异")
    elif diff > 0:
        print(f"\n结论: 配置 B 优于配置 A (+{diff:.3f})")
    else:
        print(f"\n结论: 配置 A 优于配置 B (+{-diff:.3f})")

    print("\n注意: 当前为简化模拟。生产环境应接入真实的 retrieval pipeline 和 RAGAS 评分。")


if __name__ == "__main__":
    main()

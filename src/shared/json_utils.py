"""鲁棒 JSON 解析工具 — 用于解析 LLM 输出。

P2-2: 抽取 exam_engine._parse_json_response 与 rerank.py 的重复 JSON 解析逻辑。
统一处理 markdown code fence 去除 + json.loads + 正则兜底。
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_llm_json(response: str, label: str = "JSON", expect_list: bool = False) -> list | dict:
    """鲁棒 JSON 解析：去 markdown code fence → json.loads → 正则兜底。

    Args:
        response: LLM 原始输出
        label: 用于错误提示的标签（如 "题目"、"批改结果"）
        expect_list: True 时正则兜底只匹配数组 [.*]，False 时匹配 [.*] 或 {.*}

    Returns:
        解析后的 list 或 dict

    Raises:
        ValueError: 无法解析为 JSON
    """
    response = response.strip()
    # 鲁棒去除 code fence（支持有无换行）
    response = re.sub(r"^```(?:json)?\s*\n?", "", response)
    response = re.sub(r"\n?\s*```\s*$", "", response)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # 正则兜底：提取第一个 JSON 数组或对象
        pattern = r"\[.*\]" if expect_list else r"(\[.*\]|\{.*\})"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"LLM 生成的{label}无法解析为 JSON: {response[:500]}")


def try_parse_llm_json(response: str, default=None) -> list | dict | None:
    """尝试解析 LLM JSON，失败时返回 default（不抛异常）。

    适用于 rerank 等容错场景 — 解析失败时降级而非中断。
    """
    try:
        return parse_llm_json(response, expect_list=True)
    except (ValueError, json.JSONDecodeError):
        logger.warning(f"json_parse_failed response={response[:200]}")
        return default

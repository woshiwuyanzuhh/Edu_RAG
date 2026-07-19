"""医疗健康文档清洗器 — 过滤免责声明、医院信息、药品广告。

适用场景：医学文献、健康科普、临床指南、药品说明书。
保留：医学术语、剂量、适应症、临床数据。
"""

import re

from src.ingress.cleaners.base import BaseCleaner


class MedicalCleaner(BaseCleaner):
    """医疗健康文档专用清洗器。"""

    def clean(self, text: str) -> str:
        text = super().clean(text)
        return self._filter_lines(
            text,
            [
                self._is_disclaimer,
                self._is_hospital_info,
                self._is_drug_ad,
                self._is_consult_hint,
            ],
        )

    @staticmethod
    def _is_disclaimer(line: str) -> bool:
        """医疗免责声明。"""
        keywords = [
            "仅供参考",
            "不能替代",
            "不构成医疗建议",
            "请咨询医生",
            "请遵医嘱",
            "本内容不作为",
            "最终解释权",
        ]
        return any(kw in line for kw in keywords)

    @staticmethod
    def _is_hospital_info(line: str) -> bool:
        """医院地址/电话/挂号信息行。"""
        patterns = [
            r"挂号(?:电话|热线)?\s*[:：]?\s*\d{3,}",
            r"咨询电话\s*[:：]?\s*\d{3,}",
            r"医院地址\s*[:：]",
            r"乘车路线",
            r"门诊时间\s*[:：]",
        ]
        return any(re.search(p, line) for p in patterns)

    @staticmethod
    def _is_drug_ad(line: str) -> bool:
        """药品/保健品广告行。"""
        patterns = [
            r"疗效显著",
            r"药到病除",
            r"祖传秘方",
            r"包治百病",
            r"无效退款",
            r"买\s*\d+\s*送\s*\d+",
            r"特价\s*[:：]?\s*\d+",
            r"扫码.*(?:咨询|领取|优惠)",
        ]
        return any(re.search(p, line) for p in patterns)

    @staticmethod
    def _is_consult_hint(line: str) -> bool:
        """在线咨询引导行。"""
        keywords = ["在线咨询", "免费咨询", "一对一咨询", "点击咨询", "立即咨询"]
        return any(kw in line for kw in keywords)

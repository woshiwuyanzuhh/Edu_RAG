"""金融财经文档清洗器 — 过滤风险提示、免责声明、股票代码刷屏。

适用场景：券商研报、财报、理财产品说明、财经资讯。
保留：财务数据、分析结论、指标。
"""

import re

from src.ingress.cleaners.base import BaseCleaner


class FinanceCleaner(BaseCleaner):
    """金融财经文档专用清洗器。"""

    def clean(self, text: str) -> str:
        text = super().clean(text)
        return self._filter_lines(
            text,
            [
                self._is_risk_disclaimer,
                self._is_stock_code_spam,
                self._is_disclaimer_short,
            ],
        )

    @staticmethod
    def _is_risk_disclaimer(line: str) -> bool:
        """风险提示/免责声明行。"""
        keywords = [
            "风险提示",
            "投资有风险",
            "入市需谨慎",
            "免责声明",
            "不构成投资建议",
            "仅供参考，不构成",
            "据此操作，风险自担",
            "请谨慎决策",
        ]
        return any(kw in line for kw in keywords)

    @staticmethod
    def _is_stock_code_spam(line: str) -> bool:
        """股票代码刷屏行：一行全是 6 位数字代码。"""
        # 匹配 6 位数字代码（A股），且行内代码数量 >= 3
        codes = re.findall(r"\b\d{6}\b", line)
        if len(codes) < 3:
            return False
        # 代码占行的比例 > 50% 才过滤
        code_chars = sum(len(c) for c in codes)
        return code_chars / max(len(line), 1) > 0.5

    @staticmethod
    def _is_disclaimer_short(line: str) -> bool:
        """短免责声明行（机构落款式）。

        注意：使用完整子串匹配，避免正则 `?` 元字符导致每个字可选从而过度匹配。
        """
        if len(line) > 25:
            return False
        # 完整短语匹配，避免正则元字符 ? 把每个汉字都变成可选
        keywords = [
            "本报告仅供参考",
            "本报告供参考",
            "分析师承诺",
            "评级标准",
        ]
        return any(kw in line for kw in keywords)

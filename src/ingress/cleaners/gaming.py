"""游戏攻略清洗器 — 过滤论坛签名/广告/纯emoji行。"""
import re
from src.ingress.cleaners.base import BaseCleaner


class GamingCleaner(BaseCleaner):
    """游戏攻略专用清洗器。"""

    def clean(self, text: str) -> str:
        text = super().clean(text)
        text = self._clean_gaming(text)
        return text

    @staticmethod
    def _clean_gaming(text: str) -> str:
        lines = text.split("\n")
        kept = []
        for line in lines:
            stripped = line.strip()
            if GamingCleaner._is_forum_signature(stripped):
                continue
            if GamingCleaner._is_ad(stripped):
                continue
            if GamingCleaner._is_emoji_spam(stripped):
                continue
            kept.append(line)
        return "\n".join(kept)

    @staticmethod
    def _is_forum_signature(line: str) -> bool:
        patterns = [
            r"——来自\S+客户端",
            r"回复可见",
            r"本帖最后由.*编辑",
            r"收藏\s+点赞\s+举报",
            r"编辑于\s*\d{4}[-/]\d",
            r"发自\s+\S+",
            r"发表于\s+\d{4}",
        ]
        return any(re.search(p, line) for p in patterns)

    @staticmethod
    def _is_ad(line: str) -> bool:
        patterns = [
            r"[Vv][Xx][:：]\s*\w+",
            r"加[群Qq]\s*\d{5,}",
            r"[Qq][Qq]\s*[:：]?\s*\d{5,}",
            r"微信号?\s*[:：]\s*\w+",
            r"关注[公众号微博]",
            r"扫码\s*(关注|加入|领取)",
        ]
        return any(re.search(p, line) for p in patterns)

    @staticmethod
    def _is_emoji_spam(line: str) -> bool:
        cjk = len(re.findall(r"[一-鿿]", line)) / max(len(line), 1)
        latin = len(re.findall(r"[a-zA-Z]", line)) / max(len(line), 1)
        if cjk + latin > 0.1:
            return False
        return len(line.strip()) > 0

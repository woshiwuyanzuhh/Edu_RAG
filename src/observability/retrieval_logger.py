"""检索日志记录器 — 每次 QA 请求导出结构化日志供离线评估。

Phase 4 P3-5: 数据飞轮的基础 — 线上服务导出检索日志，离线评估使用。
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class RetrievalLogger:
    """检索日志记录器 — 将每次 QA 的完整数据写入 JSON Lines 文件。

    每条记录包含：timestamp, query, chunks (scores+texts), answer, user_feedback
    """

    def __init__(self, log_dir: str | None = None):
        if log_dir:
            self._log_dir = Path(log_dir)
        else:
            self._log_dir = Path(__file__).resolve().parent.parent.parent / "data" / "retrieval_logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    async def log(
        self,
        query: str,
        chunks: list[dict],
        answer: str,
        session_id: str | None = None,
        feedback: dict | None = None,
    ) -> None:
        """记录一条检索日志（P2: aiofiles 异步写，避免阻塞事件循环）。

        Args:
            query: 用户问题
            chunks: [{"text": str, "score": float, "doc_id": ..., "chunk_index": ...}]
            answer: LLM 生成的回答
            session_id: 会话 ID
            feedback: {"rating": 1|0, "comment": str} 或 None
        """
        # 同一天的日志写入同一个文件
        date_str = datetime.utcnow().strftime("%Y%m%d")
        log_file = self._log_dir / f"retrieval_{date_str}.jsonl"

        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "query": query,
            "chunks": [
                {
                    "text": c.get("text", "")[:300],
                    "score": c.get("score", 0),
                    "doc_id": c.get("doc_id", "?"),
                    "chunk_index": c.get("chunk_index", 0),
                }
                for c in chunks
            ],
            "answer": answer[:500],
            "session_id": session_id,
            "feedback": feedback,
        }

        try:
            # P2: aiofiles 异步写，避免在 async QA 路径中阻塞事件循环
            import aiofiles

            async with aiofiles.open(log_file, "a", encoding="utf-8") as f:
                await f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"retrieval_log_write_failed error={e}")


# 全局实例
retrieval_logger = RetrievalLogger()

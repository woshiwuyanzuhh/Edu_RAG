"""上下文处理管线接口 — Generation 层 Pre-Generation 阶段的可插拔步骤链。

解决问题：原则 #3 — 所有增强必须是可插拔管线（Pluggable Pipeline），
而非硬编码的 if-else 链。

风格统一：与同包其他接口一致，使用 ABC + @abstractmethod。
"""

from abc import ABC, abstractmethod


class IContextProcessor(ABC):
    """上下文处理器抽象 — 管线中的单个步骤。

    每个步骤接收 chunks 列表和原始 query，返回处理后的 chunks 列表。
    步骤可以：过滤、压缩、重排、验证。

    约束：
        - 输入输出类型一致：list[dict] → list[dict]
        - 幂等：对空列表返回空列表
        - 无副作用：不修改外部状态
    """

    @abstractmethod
    async def process(self, chunks: list[dict], query: str) -> list[dict]:
        """处理 chunks 列表。

        Args:
            chunks: [{"text": str, "score": float, "metadata": dict}, ...]
            query: 用户原始查询

        Returns:
            处理后的 chunks 列表（可能数量减少、内容缩短、顺序改变）
        """
        ...

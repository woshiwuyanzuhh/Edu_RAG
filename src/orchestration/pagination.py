"""
统一分页工具。

解决问题 #8: 所有列表接口强制分页。
"""
import math
from typing import TypeVar

from src.shared.models.schemas import PaginatedResponse

T = TypeVar("T")


def paginate(
    items: list[T],
    total: int,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[T]:
    """构建分页响应。

    Args:
        items: 当前页数据
        total: 总数
        page: 当前页码（1-based）
        page_size: 每页数量

    Returns:
        PaginatedResponse 对象
    """
    pages = max(1, math.ceil(total / page_size))
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def get_offset_limit(page: int = 1, page_size: int = 20) -> tuple[int, int]:
    """计算 SQL 的 offset 和 limit。

    Args:
        page: 页码 (1-based)
        page_size: 每页数量

    Returns:
        (offset, limit) 元组
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    return (page - 1) * page_size, page_size

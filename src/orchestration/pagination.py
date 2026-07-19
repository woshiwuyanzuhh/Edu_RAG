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


# P2-2: 通用分页查询 — 抽取 4 个列表端点的 count + select + offset/limit 重复模式
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.ext.asyncio import AsyncSession


async def paginated_select(
    db: "AsyncSession",
    model: type,
    page: int = 1,
    page_size: int = 20,
    where: "ColumnElement[bool] | None" = None,
    order_by: Any = None,
    serializer: Callable[[Any], Any] | None = None,
) -> PaginatedResponse:
    """P2-2: 通用分页查询 — 封装 count + select + offset/limit + serialize。

    Args:
        db: 异步数据库会话
        model: ORM 模型类
        page: 页码 (1-based)
        page_size: 每页数量（已由 API 层 Query 约束 le=100）
        where: 可选的 WHERE 条件（SQLAlchemy ColumnElement）
        order_by: 可选的排序字段（如 Model.created_at.desc()）
        serializer: 可选的行序列化函数（ORM 对象 → dict）

    Returns:
        PaginatedResponse，可直接 .model_dump() 返回给前端
    """
    from sqlalchemy import func, select

    # count 查询
    count_query = select(func.count(model.id))
    if where is not None:
        count_query = count_query.where(where)
    total = (await db.execute(count_query)).scalar() or 0

    # select 查询
    query = select(model)
    if where is not None:
        query = query.where(where)
    if order_by is not None:
        query = query.order_by(order_by)

    offset, limit = get_offset_limit(page, page_size)
    result = await db.execute(query.offset(offset).limit(limit))
    rows = result.scalars().all()

    items = [serializer(row) for row in rows] if serializer else list(rows)
    return paginate(items, total, page, page_size)

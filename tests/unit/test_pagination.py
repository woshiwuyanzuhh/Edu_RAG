"""统一分页工具测试 — src/orchestration/pagination.py。"""
import pytest
from src.orchestration.pagination import paginate, get_offset_limit


class TestGetOffsetLimit:
    """get_offset_limit — SQL offset/limit 计算。"""

    def test_first_page(self):
        offset, limit = get_offset_limit(page=1, page_size=20)
        assert offset == 0
        assert limit == 20

    def test_second_page(self):
        offset, limit = get_offset_limit(page=2, page_size=20)
        assert offset == 20
        assert limit == 20

    def test_third_page(self):
        offset, limit = get_offset_limit(page=3, page_size=10)
        assert offset == 20
        assert limit == 10

    def test_zero_page_clamped_to_1(self):
        offset, limit = get_offset_limit(page=0, page_size=20)
        assert offset == 0
        assert limit == 20

    def test_negative_page_clamped_to_1(self):
        offset, limit = get_offset_limit(page=-5, page_size=20)
        assert offset == 0
        assert limit == 20

    def test_page_size_clamped_to_100(self):
        offset, limit = get_offset_limit(page=1, page_size=200)
        assert limit == 100

    def test_zero_page_size_clamped_to_1(self):
        offset, limit = get_offset_limit(page=1, page_size=0)
        assert limit == 1

    def test_default_values(self):
        offset, limit = get_offset_limit()
        assert offset == 0
        assert limit == 20


class TestPaginate:
    """paginate — 构建分页响应。"""

    def test_single_page(self):
        items = [1, 2, 3]
        resp = paginate(items, total=3, page=1, page_size=20)
        assert resp.items == items
        assert resp.total == 3
        assert resp.page == 1
        assert resp.page_size == 20
        assert resp.pages == 1

    def test_multi_page(self):
        items = list(range(20))
        resp = paginate(items, total=45, page=1, page_size=20)
        assert len(resp.items) == 20
        assert resp.total == 45
        assert resp.pages == 3

    def test_last_page(self):
        items = list(range(5))
        resp = paginate(items, total=45, page=3, page_size=20)
        assert len(resp.items) == 5
        assert resp.page == 3
        assert resp.pages == 3

    def test_empty_list(self):
        resp = paginate([], total=0, page=1, page_size=20)
        assert resp.items == []
        assert resp.total == 0
        assert resp.pages == 1  # 至少 1 页

    def test_total_one_with_large_page(self):
        resp = paginate([1], total=1, page=1, page_size=100)
        assert resp.pages == 1
        assert resp.total == 1

    def test_page_out_of_range(self):
        """页码超出范围 — paginate 不做校验，由调用方处理。"""
        resp = paginate([], total=10, page=999, page_size=20)
        assert resp.page == 999
        assert resp.pages == 1

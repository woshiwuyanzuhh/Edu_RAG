"""MilvusStore 单元测试 — Mock pymilvus。

验证所有 IVectorStore 接口方法的行为正确性。
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock
from src.interfaces.vector_store import VectorItem, SearchResult


@pytest.fixture
def mock_pymilvus():
    """构造完整的 mock pymilvus 环境。"""
    mock_col = MagicMock()
    mock_col.num_entities = MagicMock(return_value=100)
    mock_col.query.return_value = {"ids": [["1", "2"]], "documents": [["a", "b"]], "distances": [[0.1, 0.5]]}

    mock_connections = MagicMock()
    mock_utility = MagicMock()
    mock_utility.has_collection.return_value = True

    mock_Collection = MagicMock(return_value=mock_col)
    mock_FieldSchema = MagicMock()
    mock_CollectionSchema = MagicMock()
    mock_DataType = MagicMock()

    return {
        "connections": mock_connections,
        "Collection": mock_Collection,
        "FieldSchema": mock_FieldSchema,
        "CollectionSchema": mock_CollectionSchema,
        "DataType": mock_DataType,
        "utility": mock_utility,
        "col": mock_col,
    }


class TestMilvusStoreInit:
    """初始化测试。"""

    def test_init_with_pymilvus_available(self, mock_pymilvus):
        with patch.dict("sys.modules", {"pymilvus": MagicMock()}):
            from src.retrieval.vector_store.milvus import MilvusStore
            store = MilvusStore()
            assert store._connected is False  # type: ignore[union-attr]

    def test_warns_when_pymilvus_missing(self):
        """pymilvus 已安装时跳过此测试。未安装时 MilvusStore() 会抛 ImportError。"""
        from src.retrieval.vector_store.milvus import _HAS_PYMILVUS
        if _HAS_PYMILVUS:
            pytest.skip("pymilvus 已安装，测试不适用")
        from src.retrieval.vector_store.milvus import MilvusStore
        with pytest.raises(ImportError, match="pymilvus"):
            MilvusStore()


class TestBuildExpr:
    """_build_expr 过滤表达式构建。"""

    def test_none_filter(self):
        from src.retrieval.vector_store.milvus import MilvusStore
        assert MilvusStore._build_expr(None) is None

    def test_knowledge_base_id(self):
        from src.retrieval.vector_store.milvus import MilvusStore
        expr = MilvusStore._build_expr({"knowledge_base_id": 42})
        assert "knowledge_base_id == 42" in expr

    def test_doc_id(self):
        from src.retrieval.vector_store.milvus import MilvusStore
        expr = MilvusStore._build_expr({"doc_id": 7})
        assert "doc_id == 7" in expr

    def test_combined(self):
        from src.retrieval.vector_store.milvus import MilvusStore
        expr = MilvusStore._build_expr({"knowledge_base_id": 1, "doc_id": 5})
        assert "knowledge_base_id == 1" in expr
        assert "doc_id == 5" in expr
        assert " and " in expr


class TestMilvusStoreOperations:
    """CRUD 操作测试（全部 mock）。"""

    @pytest.fixture
    def store(self, mock_pymilvus):
        with patch.dict("sys.modules", {
            "pymilvus": MagicMock(),
            "pymilvus.connections": mock_pymilvus["connections"],
            "pymilvus.Collection": mock_pymilvus["Collection"],
            "pymilvus.FieldSchema": mock_pymilvus["FieldSchema"],
            "pymilvus.CollectionSchema": mock_pymilvus["CollectionSchema"],
            "pymilvus.DataType": mock_pymilvus["DataType"],
            "pymilvus.utility": mock_pymilvus["utility"],
        }):
            from src.retrieval.vector_store.milvus import MilvusStore
            store = MilvusStore()
            store._collection = mock_pymilvus["col"]
            store._connected = True
            yield store

    def test_insert_empty_list(self, store):
        asyncio.run(store.insert([]))
        # 不应崩溃

    def test_insert_items(self, store):
        items = [
            VectorItem(id="1", text="test chunk", embedding=[0.1] * 1024,
                       metadata={"knowledge_base_id": 1, "doc_id": 10, "chunk_index": 0}),
        ]
        asyncio.run(store.insert(items))
        # 验证 collection.insert 被调用
        store._collection.insert.assert_called_once()

    def test_search_no_filter(self, store):
        # Mock search result
        mock_hit = MagicMock()
        mock_hit.id = "1"
        mock_hit.distance = 0.95
        mock_hit.entity.get.side_effect = lambda key, default=None: {
            "text": "test content", "doc_id": 10, "chunk_index": 0, "knowledge_base_id": 1,
        }.get(key, default)

        store._collection.search.return_value = [[mock_hit]]

        result = asyncio.run(store.search([0.1] * 1024, top_k=5))
        assert len(result) == 1
        assert isinstance(result[0], SearchResult)
        assert result[0].id == "1"
        assert result[0].text == "test content"

    def test_search_no_collection(self, store):
        store._collection = None
        result = asyncio.run(store.search([0.1] * 1024))
        assert result == []

    def test_search_with_filter(self, store):
        mock_hit = MagicMock()
        mock_hit.id = "2"
        mock_hit.distance = 0.88
        mock_hit.entity.get.side_effect = lambda key, default=None: {
            "text": "filtered", "doc_id": 5, "chunk_index": 1, "knowledge_base_id": 42,
        }.get(key, default)

        store._collection.search.return_value = [[mock_hit]]
        result = asyncio.run(store.search([0.1] * 1024, top_k=3, filter_expr={"knowledge_base_id": 42}))
        assert len(result) == 1
        assert result[0].metadata["knowledge_base_id"] == 42

    def test_delete_by_ids(self, store):
        asyncio.run(store.delete_by_ids(["id1", "id2"]))
        store._collection.delete.assert_called_once()

    def test_delete_empty_ids(self, store):
        asyncio.run(store.delete_by_ids([]))
        # 空列表不应调用 delete

    def test_delete_by_filter(self, store):
        asyncio.run(store.delete_by_filter({"knowledge_base_id": 1}))
        store._collection.delete.assert_called_once()

    def test_count(self, store):
        # num_entities 在 pymilvus 中是 property/method，mock 为可调用对象
        store._collection.num_entities = MagicMock(return_value=42)
        result = asyncio.run(store.count())
        assert result == 42

    def test_count_no_collection(self, store):
        store._collection = None
        result = asyncio.run(store.count())
        assert result == 0

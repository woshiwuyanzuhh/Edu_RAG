"""题库引擎测试 — src/generation/exam_engine.py。"""
import pytest
from unittest.mock import AsyncMock
from src.generation.exam_engine import _parse_json_response, _score_summary


class TestParseJsonResponse:
    def test_plain_json_array(self):
        result = _parse_json_response('[{"name":"test"}]', "测试")
        assert isinstance(result, list)
        assert result[0]["name"] == "test"

    def test_plain_json_object(self):
        result = _parse_json_response('{"key":"value"}', "测试")
        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_code_fence_with_newline(self):
        result = _parse_json_response('```json\n[{"a":1}]\n```', "测试")
        assert isinstance(result, list)
        assert result[0]["a"] == 1

    def test_code_fence_single_line(self):
        result = _parse_json_response('```[{"a":1}]```', "测试")
        assert isinstance(result, list)

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            _parse_json_response("不是JSON", "测试")

    def test_json_with_regex_fallback(self):
        result = _parse_json_response('一些文字 [{"b":2}] 更多文字', "测试")
        assert isinstance(result, list)
        assert result[0]["b"] == 2


class TestScoreSummary:
    def test_excellent(self):
        assert "优秀" in _score_summary(95)

    def test_good(self):
        assert "良好" in _score_summary(80)

    def test_pass(self):
        assert "及格" in _score_summary(65)

    def test_fail(self):
        assert "加强学习" in _score_summary(40)

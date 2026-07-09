"""安全模块测试 — src/shared/security.py。"""
import pytest
from unittest.mock import MagicMock, PropertyMock
from src.shared.security import (
    WEAK_PASSWORDS,
    validate_secrets,
    print_security_warnings,
)


def _mock_settings(
    llm_key="sk-valid-key-1234567890abcdef",
    mysql_pwd="strong-password-123",
    redis_pwd="",
    app_key="",
):
    """构造 mock Settings 对象。"""
    settings = MagicMock()

    # LLM
    type(settings.llm).api_key = PropertyMock()
    settings.llm.api_key.get_secret_value.return_value = llm_key

    # MySQL
    type(settings.mysql).password = PropertyMock()
    settings.mysql.password.get_secret_value.return_value = mysql_pwd

    # Redis
    type(settings.redis).password = PropertyMock()
    settings.redis.password.get_secret_value.return_value = redis_pwd

    # App
    type(settings.app).api_key = PropertyMock()
    settings.app.api_key.get_secret_value.return_value = app_key

    return settings


class TestValidateSecrets:
    """启动时密钥校验。"""

    def test_all_good_no_warnings(self):
        settings = _mock_settings(
            llm_key="sk-valid-key-1234567890abcdef",
            mysql_pwd="strong-password-123",
            redis_pwd="redis-secure-pass",
            app_key="a-very-long-api-key-that-is-at-least-32-chars",
        )
        warnings = validate_secrets(settings)
        assert warnings == []

    def test_default_llm_key_warns(self):
        settings = _mock_settings(llm_key="sk-xxx")
        warnings = validate_secrets(settings)
        assert any("LLM API Key 未配置" in w for w in warnings)

    def test_empty_llm_key_warns(self):
        settings = _mock_settings(llm_key="")
        warnings = validate_secrets(settings)
        assert any("LLM API Key 未配置" in w for w in warnings)

    def test_short_llm_key_warns(self):
        settings = _mock_settings(llm_key="sk-short")
        warnings = validate_secrets(settings)
        assert any("格式可疑" in w for w in warnings)

    def test_weak_mysql_password_warns(self):
        for pwd in ["123456", "password", "root", "admin"]:
            settings = _mock_settings(mysql_pwd=pwd)
            warnings = validate_secrets(settings)
            assert any(f"弱口令 '{pwd}'" in w for w in warnings), f"应警告弱密码: {pwd}"

    def test_empty_mysql_password_warns(self):
        settings = _mock_settings(mysql_pwd="")
        warnings = validate_secrets(settings)
        assert any("MySQL 密码为空" in w for w in warnings)

    def test_redis_no_password_warns(self):
        settings = _mock_settings(redis_pwd="")
        warnings = validate_secrets(settings)
        assert any("Redis 无密码保护" in w for w in warnings)

    def test_weak_redis_password_warns(self):
        settings = _mock_settings(redis_pwd="123456")
        warnings = validate_secrets(settings)
        assert any("弱口令" in w for w in warnings)

    def test_empty_api_key_warns(self):
        settings = _mock_settings(app_key="")
        warnings = validate_secrets(settings)
        assert any("APP_API_KEY 未设置" in w for w in warnings)

    def test_short_api_key_warns(self):
        settings = _mock_settings(app_key="short")
        warnings = validate_secrets(settings)
        assert any("APP_API_KEY 过短" in w for w in warnings)


class TestWeakPasswords:
    """弱密码字典完整性。"""

    def test_common_passwords_in_set(self):
        for pwd in ["123456", "password", "admin", "root", "12345678",
                     "123456789", "qwerty", "abc123", "111111", "000000"]:
            assert pwd in WEAK_PASSWORDS


class TestPrintSecurityWarnings:
    """格式化输出安全警告 — 不抛异常即可。"""

    def test_no_warnings(self):
        print_security_warnings([])  # 不应抛异常

    def test_with_warnings(self):
        print_security_warnings(["警告1", "警告2"])  # 不应抛异常

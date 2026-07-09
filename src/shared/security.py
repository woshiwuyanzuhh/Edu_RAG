"""
安全模块 — 密钥校验、密码强度检测、敏感信息脱敏。
"""
import logging

from src.shared.config import Settings

logger = logging.getLogger(__name__)


# ── 弱密码模式 ──
WEAK_PASSWORDS = {
    "123456", "password", "admin", "root", "12345678",
    "123456789", "qwerty", "abc123", "111111", "000000",
}


def validate_secrets(settings: Settings) -> list[str]:
    """启动时校验密钥和密码安全性，返回警告列表。"""
    warnings: list[str] = []

    # 1. LLM API Key 检查
    llm_key = settings.llm.api_key.get_secret_value()
    if llm_key in ("sk-xxx", "", "your-api-key"):
        warnings.append("LLM API Key 未配置（使用默认值），LLM 调用将失败")
    elif llm_key.startswith("sk-") and len(llm_key) < 20:
        warnings.append("LLM API Key 格式可疑（过短）")

    # 2. MySQL 密码检查
    mysql_pwd = settings.mysql.password.get_secret_value()
    if mysql_pwd in WEAK_PASSWORDS:
        warnings.append(f"MySQL 密码为弱口令 '{mysql_pwd}'，请立即修改")
    if mysql_pwd == "":
        warnings.append("MySQL 密码为空，存在安全风险")

    # 3. Redis 密码检查
    redis_pwd = settings.redis.password.get_secret_value()
    if redis_pwd == "":
        warnings.append("Redis 无密码保护，生产环境请设置密码")
    elif redis_pwd in WEAK_PASSWORDS:
        warnings.append(f"Redis 密码为弱口令 '{redis_pwd}'，请立即修改")

    # 4. 应用 API Key
    app_key = settings.app.api_key.get_secret_value()
    if app_key == "":
        warnings.append("APP_API_KEY 未设置，API 鉴权将跳过（所有端点公开）")
    elif len(app_key) < 16:
        warnings.append("APP_API_KEY 过短（建议 ≥32 字符）")

    return warnings


def print_security_warnings(warnings: list[str]) -> None:
    """格式化输出安全警告。"""
    if not warnings:
        logger.info("✅ 安全配置检查通过")
        return

    logger.warning("=" * 55)
    logger.warning("  ⚠️  安全警告")
    logger.warning("=" * 55)
    for i, w in enumerate(warnings, 1):
        logger.warning(f"  {i}. {w}")
    logger.warning("=" * 55)

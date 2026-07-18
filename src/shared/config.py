"""
全局配置管理 — Pydantic BaseSettings。

优势（对比 v1.0 os.getenv 散落调用）：
    1. 启动时全量校验，缺失/格式错误立刻报错
    2. SecretStr 自动隐藏敏感信息
    3. 类型安全，IDE 自动补全
    4. 单一来源，不再散落各处
"""
from pathlib import Path
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class LLMConfig(BaseSettings):
    """LLM 配置。"""
    api_key: SecretStr = Field(default=SecretStr("sk-xxx"), description="LLM API 密钥")
    base_url: str = Field(default="https://api.deepseek.com/v1", description="LLM API 地址")
    model: str = Field(default="deepseek-chat", description="模型名")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    retry_backoff: float = Field(default=2.0, ge=1.0, description="退避倍数")


class EmbeddingConfig(BaseSettings):
    """Embedding 配置。"""
    provider: str = Field(default="api", pattern="^(api|local)$", description="local 或 api")
    model: str = Field(default="bge-m3", description="Embedding 模型名")
    # API 模式
    api_base_url: str = Field(default="http://localhost:11434/v1", description="Embedding API 地址")
    api_key: SecretStr = Field(default=SecretStr("ollama"), description="Embedding API 密钥")
    # 本地模式
    local_model: str = Field(default="shibing624/text2vec-base-chinese", description="本地 sentence-transformers 模型名")

    @field_validator("api_base_url")
    @classmethod
    def url_must_end_with_v1(cls, v: str) -> str:
        if v and not v.rstrip("/").endswith("/v1"):
            raise ValueError(f"Embedding API URL 应以 /v1 结尾: {v}")
        return v


class VectorStoreConfig(BaseSettings):
    """向量数据库配置。"""
    provider: str = Field(default="chroma", pattern="^(chroma|milvus)$", description="chroma 或 milvus")
    # ChromaDB
    chroma_path: str = Field(default="", description="ChromaDB 持久化路径")
    # Milvus
    milvus_host: str = Field(default="localhost")
    milvus_port: int = Field(default=19530, ge=1, le=65535)

    def get_chroma_path(self) -> str:
        if self.chroma_path:
            return self.chroma_path
        return str(PROJECT_ROOT / "data" / "chroma")


class MySQLConfig(BaseSettings):
    """MySQL 配置。"""
    host: str = Field(default="localhost")
    port: int = Field(default=3306, ge=1, le=65535)
    user: str = Field(default="root")
    password: SecretStr = Field(default=SecretStr(""))
    database: str = Field(default="edu_rag")
    pool_size: int = Field(default=30, ge=1, le=100, description="连接池大小（P1-C7: 10→30 支撑高并发）")
    max_overflow: int = Field(default=50, ge=0, le=100, description="连接池溢出上限（P1-C7 新增）")
    pool_recycle: int = Field(default=3600, ge=60)
    pool_pre_ping: bool = Field(default=True, description="连接前 ping 检测活性，避免使用失效连接（P1-C7 新增）")

    @property
    def url(self) -> str:
        return (
            f"mysql+aiomysql://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?charset=utf8mb4"
        )

    @property
    def sync_url(self) -> str:
        """同步 URL（用于 alembic 等工具）。"""
        return (
            f"mysql+pymysql://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?charset=utf8mb4"
        )


class RedisConfig(BaseSettings):
    """Redis 配置。"""
    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)
    password: SecretStr = Field(default=SecretStr(""))
    default_ttl: int = Field(default=3600, ge=60, description="默认缓存 TTL（秒）")

    @property
    def connection_kwargs(self) -> dict:
        kw = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "decode_responses": True,
        }
        pwd = self.password.get_secret_value()
        if pwd:
            kw["password"] = pwd
        return kw


class StorageConfig(BaseSettings):
    """文件存储配置（P1-D2）。"""
    provider: str = Field(default="local", pattern="^(local|object)$", description="local 或 object（S3 兼容）")
    endpoint: str = Field(default="", description="对象存储 endpoint（留空用默认 S3）")
    access_key: SecretStr = Field(default=SecretStr(""))
    secret_key: SecretStr = Field(default=SecretStr(""))
    bucket: str = Field(default="")
    region: str = Field(default="")


class RetrievalConfig(BaseSettings):
    """检索参数配置 — 可调节的检索管线参数。"""
    min_score: float = Field(default=0.3, ge=0.0, le=1.0, description="最低分数阈值")
    fusion_alpha: float = Field(default=0.7, ge=0.0, le=1.0, description="LLM 分数融合权重")
    max_chunks: int = Field(default=10, ge=1, le=50, description="最多保留的块数")
    recall_multiplier: int = Field(default=10, ge=2, le=20, description="粗排候选倍数")


class GenerationConfig(BaseSettings):
    """Generation 配置 — Feature Flags + 管线步骤开关。"""
    # 上下文增强管线步骤开关（Phase 2-3 使用）
    enable_lost_middle: bool = Field(default=True, description="Lost in the Middle 注意力重排")
    enable_relevance_filter: bool = Field(default=False, description="LLM 相关性过滤（需额外 LLM 调用）")
    enable_compression: bool = Field(default=False, description="LLM 语义压缩（需额外 LLM 调用）")
    enable_hyde: bool = Field(default=False, description="HyDE 假设文档嵌入（Phase 4）")
    enable_refuse: bool = Field(default=True, description="低置信度时拒绝编造")


class IngressConfig(BaseSettings):
    """Ingestion 配置。"""
    chunk_size: int = Field(default=800, ge=100, le=5000, description="默认分块大小")
    chunk_overlap: int = Field(default=100, ge=0, le=1000, description="默认块间重叠")


class AppConfig(BaseSettings):
    """应用配置。"""
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    upload_dir: str = Field(default="")
    max_upload_size_mb: int = Field(default=50, ge=1, le=500)
    debug: bool = Field(default=False)
    async_ingestion: bool = Field(default=False, description="P1-C5: 文档入库走 ARQ 异步队列（生产 True，开发 False 同步）")
    api_key: SecretStr = Field(default=SecretStr(""), description="API 鉴权密钥（为空则跳过鉴权）")
    cors_origins: list[str] = Field(default=["http://localhost:5173"], description="CORS 允许的来源")

    def get_upload_dir(self) -> str:
        if self.upload_dir:
            return self.upload_dir
        return str(PROJECT_ROOT / "data")


class Settings(BaseSettings):
    """全局配置单例。"""
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    mysql: MySQLConfig = Field(default_factory=MySQLConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    ingress_cfg: IngressConfig = Field(default_factory=IngressConfig)
    app: AppConfig = Field(default_factory=AppConfig)


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（带缓存）。"""
    return Settings()


# 模块级便捷访问
settings = get_settings()

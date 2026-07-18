"""文件存储抽象（P1-D2）。

支持本地磁盘（开发/单机）和 S3 兼容对象存储（生产/多实例/容灾）。
通过 STORAGE__PROVIDER 切换，调用方不感知存储位置。

对象存储适配：AWS S3 / 腾讯 COS / 阿里 OSS / MinIO 均兼容 S3 API。
对象存储需 boto3（延迟导入，未配置 object 时不强制依赖）。

设计说明：
    当前架构在文档上传时先写本地临时文件（边读边写 + 魔数校验），
    再由 storage.save 决定最终去向：本地保留 / 上传对象存储后删本地。
    Document.file_path 存储统一 key（本地=绝对路径，对象存储=s3:// URI）。
"""
from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """文件存储后端抽象。"""

    @abstractmethod
    async def save(self, local_path: str, key: str) -> str:
        """保存本地文件到存储，返回存储 key（写入 Document.file_path）。"""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除存储中的文件。"""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """文件是否存在。"""


class LocalStorage(StorageBackend):
    """本地磁盘存储（默认，单机/开发）。key = 绝对路径。"""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    async def save(self, local_path: str, key: str) -> str:
        # 本地存储：local_path 即最终路径，原样返回
        return local_path

    async def delete(self, key: str) -> None:
        if key and os.path.exists(key):
            await asyncio.to_thread(os.remove, key)

    async def exists(self, key: str) -> bool:
        return bool(key) and os.path.exists(key)


class ObjectStorage(StorageBackend):
    """S3 兼容对象存储（AWS S3 / 腾讯 COS / 阿里 OSS / MinIO）。

    需 boto3：pip install boto3
    文件先写本地临时文件，再上传到对象存储，返回 s3:// URI 作为 key。
    上传成功后删除本地临时文件，实现"文件不绑本地磁盘"。
    """

    def __init__(self, endpoint: str, access_key: str, secret_key: str,
                 bucket: str, region: str = "", prefix: str = "documents"):
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._region = region or "us-east-1"
        self._prefix = prefix
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3  # 延迟导入，避免强制依赖
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint or None,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
            )
        return self._client

    def _obj_key(self, local_path: str) -> str:
        return f"{self._prefix}/{Path(local_path).name}"

    def _s3_uri(self, obj_key: str) -> str:
        return f"s3://{self._bucket}/{obj_key}"

    async def save(self, local_path: str, key: str) -> str:
        obj_key = self._obj_key(local_path)
        await asyncio.to_thread(
            self._get_client().upload_file, local_path, self._bucket, obj_key
        )
        # 上传成功后删除本地临时文件，释放磁盘
        await asyncio.to_thread(os.remove, local_path)
        logger.info(f"object_storage_uploaded bucket={self._bucket} key={obj_key}")
        return self._s3_uri(obj_key)

    async def delete(self, key: str) -> None:
        if not key or not key.startswith("s3://"):
            return
        obj_key = key.replace(f"s3://{self._bucket}/", "", 1)
        await asyncio.to_thread(
            self._get_client().delete_object, Bucket=self._bucket, Key=obj_key
        )

    async def exists(self, key: str) -> bool:
        if not key or not key.startswith("s3://"):
            return False
        obj_key = key.replace(f"s3://{self._bucket}/", "", 1)
        try:
            await asyncio.to_thread(
                self._get_client().head_object, Bucket=self._bucket, Key=obj_key
            )
            return True
        except Exception:
            return False


_default_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """获取存储后端单例（懒加载，按配置选择 local / object）。"""
    global _default_storage
    if _default_storage is None:
        from src.shared.config import settings
        if settings.storage.provider == "object":
            _default_storage = ObjectStorage(
                endpoint=settings.storage.endpoint,
                access_key=settings.storage.access_key.get_secret_value(),
                secret_key=settings.storage.secret_key.get_secret_value(),
                bucket=settings.storage.bucket,
                region=settings.storage.region,
            )
            logger.info(f"storage=object bucket={settings.storage.bucket}")
        else:
            _default_storage = LocalStorage(base_dir=settings.app.get_upload_dir())
            logger.info("storage=local")
    return _default_storage

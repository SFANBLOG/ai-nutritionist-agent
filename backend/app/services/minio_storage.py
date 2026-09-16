"""对象存储服务(MinIO 优先,本地磁盘兜底)

- 配置了 MINIO_ENDPOINT 且可连接时,使用 MinIO 存储上传的体检报告等文件。
- 否则降级为本地磁盘 backend/data/uploads,接口保持一致。
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import DATA_DIR, settings

logger = logging.getLogger(__name__)

UPLOAD_DIR = DATA_DIR / "uploads"


class StorageService:
    """统一的对象存储访问层"""

    def __init__(self) -> None:
        self.endpoint = (settings.MINIO_ENDPOINT or "").strip()
        self.bucket = settings.MINIO_BUCKET
        self.secure = bool(settings.MINIO_SECURE)
        self.available = False
        self._client = None

        if self.endpoint:
            try:
                from minio import Minio
                from minio.error import S3Error  # type: ignore

                self._client = Minio(
                    self.endpoint,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=self.secure,
                )
                # 确保桶存在
                if not self._client.bucket_exists(self.bucket):
                    self._client.make_bucket(self.bucket)
                self.available = True
                logger.info("对象存储后端: MinIO(%s), bucket=%s", self.endpoint, self.bucket)
            except Exception as exc:  # pragma: no cover - 依赖外部服务
                logger.warning("MinIO 不可用,降级为本地磁盘存储: %s", exc)
                self.available = False

        if not self.available:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("对象存储后端: 本地磁盘(%s)", UPLOAD_DIR)

    # ------------------------------------------------------------------ 写入
    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """写入对象,返回对象 key"""
        if self.available and self._client is not None:
            from io import BytesIO

            self._client.put_object(
                self.bucket,
                key,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        else:
            path = UPLOAD_DIR / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return key

    # ------------------------------------------------------------------ 读取
    def get_object(self, key: str) -> Tuple[bytes, str]:
        """读取对象内容,返回 (data, content_type)"""
        if self.available and self._client is not None:
            resp = self._client.get_object(self.bucket, key)
            try:
                data = resp.read()
            finally:
                resp.close()
                resp.release_conn()
            return data, self._guess_content_type(key)
        path = UPLOAD_DIR / key
        if not path.exists():
            raise FileNotFoundError(key)
        return path.read_bytes(), self._guess_content_type(key)

    @staticmethod
    def _guess_content_type(key: str) -> str:
        suffix = Path(key).suffix.lower()
        return {
            ".pdf": "application/pdf",
            ".txt": "text/plain; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".csv": "text/csv; charset=utf-8",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(suffix, "application/octet-stream")

    def gen_key(self, filename: str) -> str:
        """生成唯一对象 key"""
        ext = Path(filename).suffix
        return f"{uuid.uuid4().hex}{ext}"


_storage_singleton: Optional[StorageService] = None


def get_storage() -> StorageService:
    global _storage_singleton
    if _storage_singleton is None:
        _storage_singleton = StorageService()
    return _storage_singleton

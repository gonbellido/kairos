"""Secure document storage with MinIO — client-level isolation and encryption."""

import hashlib
import logging
from datetime import timedelta
from typing import Optional
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from kairos.config import get_settings

logger = logging.getLogger(__name__)


class SecureStorage:
    """MinIO-backed secure storage with per-client isolation and SSE-S3 encryption."""

    BUCKET = "kairos-documents"

    def __init__(self):
        settings = get_settings()
        self._client = Minio(
            f"{settings.minio_host}:{settings.minio_port}",
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._encrypt = settings.minio_encryption
        self._ensure_bucket()

    def _ensure_bucket(self):
        if not self._client.bucket_exists(self.BUCKET):
            self._client.make_bucket(self.BUCKET)
            logger.info("Created bucket: %s", self.BUCKET)

            # Set bucket policy: private (default)
            policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self.BUCKET}/*"],
                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                }],
            }
            self._client.set_bucket_policy(self.BUCKET, __import__("json").dumps(policy))

    # ── Object path builder ──

    @staticmethod
    def _path(coach_id: str, client_id: str, filename: str) -> str:
        """Construye la ruta aislada: {coach_id}/{client_id}/{filename}"""
        safe_name = filename.replace(" ", "_").replace("/", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "._-")
        unique = uuid4().hex[:8]
        if client_id:
            return f"{coach_id}/{client_id}/{unique}_{safe_name}"
        return f"{coach_id}/{unique}_{safe_name}"

    # ── Upload ──

    def upload(
        self,
        coach_id: str,
        client_id: str,
        filename: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """Sube un documento al storage aislado del cliente. Retorna metadata."""
        object_path = self._path(coach_id, client_id, filename)
        sha = hashlib.sha256(data).hexdigest()

        extra_headers = {}
        if self._encrypt:
            from minio.sse import SseS3  # noqa
            extra_headers = {"x-amz-server-side-encryption": "AES256"}
            logger.debug("SSE-S3 encryption enabled for %s", object_path)

        try:
            from io import BytesIO
            self._client.put_object(
                self.BUCKET,
                object_path,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
                metadata={
                    "coach-id": coach_id,
                    "client-id": client_id,
                    "original-name": filename,
                    "sha256": sha,
                },
            )
            logger.info("Stored: %s (%d bytes, sha=%s)", object_path, len(data), sha[:12])
            return {
                "object_path": object_path,
                "bucket": self.BUCKET,
                "size": len(data),
                "sha256": sha,
                "encrypted": self._encrypt,
            }
        except S3Error as e:
            logger.error("MinIO upload failed: %s", e)
            raise

    # ── Download ──

    def download(self, object_path: str) -> bytes:
        """Descarga un documento por su path."""
        try:
            response = self._client.get_object(self.BUCKET, object_path)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.error("MinIO download failed: %s", e)
            raise

    # ── Presigned URL (temporary access) ──

    def presigned_get(self, object_path: str, expires_minutes: int = 15) -> str:
        """Genera una URL temporal de descarga (15 min por defecto)."""
        return self._client.presigned_get_object(
            self.BUCKET, object_path, expires=timedelta(minutes=expires_minutes)
        )

    # ── Delete ──

    def delete(self, object_path: str) -> bool:
        """Elimina un documento."""
        try:
            self._client.remove_object(self.BUCKET, object_path)
            logger.info("Deleted: %s", object_path)
            return True
        except S3Error:
            return False

    # ── List objects for a client ──

    def list_client_objects(self, coach_id: str, client_id: str = "") -> list[dict]:
        """Lista objetos de un coach (y opcionalmente un cliente específico)."""
        prefix = f"{coach_id}/"
        if client_id:
            prefix += f"{client_id}/"
        objects = []
        try:
            for obj in self._client.list_objects(self.BUCKET, prefix=prefix, recursive=True):
                objects.append({
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else "",
                })
        except S3Error:
            pass
        return objects


# Singleton
_storage: Optional[SecureStorage] = None


def get_storage() -> SecureStorage:
    global _storage
    if _storage is None:
        _storage = SecureStorage()
    return _storage

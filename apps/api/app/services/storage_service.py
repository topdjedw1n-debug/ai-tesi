"""
Storage service for centralized MinIO/S3 operations.

Replaces duplicated MinIO client code across:
- documents.py download endpoint (501 → working)
- gdpr_service.py _delete_from_storage
- document_service.py verify_file_storage + upload

Design principles:
- Async everywhere (FastAPI requirement)
- Lazy client initialization (not at import time)
- Type hints (mypy compliance)
- Error handling: S3Error → HTTPException/bool
- Path formats: s3://bucket/path or /path (auto-detect)

Created: 2025-11-29
Related to: Storage Service implementation (MVP_PLAN.md)
"""

from datetime import timedelta
from io import BytesIO
from typing import AsyncGenerator, Optional
import logging

from fastapi import HTTPException
from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Centralized MinIO/S3 storage operations."""

    def __init__(self):
        """Initialize service with lazy client loading."""
        self._client: Optional[Minio] = None

    @property
    def client(self) -> Minio:
        """
        Lazy initialization of MinIO client.

        Returns:
            Minio: Configured MinIO client
        """
        if self._client is None:
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            logger.info(f"MinIO client initialized: {settings.MINIO_ENDPOINT}")
        return self._client

    def _parse_path(self, file_path: str) -> tuple[str, str]:
        """
        Parse file path to bucket and object name.

        Supports formats:
        - s3://bucket/path/to/file
        - /path/to/file (uses default bucket)

        Args:
            file_path: File path in various formats

        Returns:
            tuple: (bucket_name, object_name)

        Raises:
            ValueError: If path format is invalid
        """
        if file_path.startswith("s3://"):
            # s3://bucket/path/to/file
            path_parts = file_path.replace("s3://", "").split("/", 1)
            if len(path_parts) != 2:
                raise ValueError(f"Invalid S3 path: {file_path}")
            return path_parts[0], path_parts[1]
        else:
            # /path/to/file or path/to/file
            object_name = file_path.lstrip("/")
            return settings.MINIO_BUCKET, object_name

    async def upload_file(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload file to MinIO.

        Args:
            object_name: Path in bucket (e.g., "documents/user_id/doc_id/file.pdf")
            data: File content as bytes
            content_type: MIME type (default: application/octet-stream)

        Returns:
            str: S3 path (s3://bucket/object_name)

        Raises:
            HTTPException: If upload fails
        """
        try:
            file_stream = BytesIO(data)
            file_size = len(data)

            logger.info(f"Uploading file: {object_name} ({file_size} bytes)")

            self.client.put_object(
                settings.MINIO_BUCKET,
                object_name,
                file_stream,
                length=file_size,
                content_type=content_type,
            )

            s3_path = f"s3://{settings.MINIO_BUCKET}/{object_name}"
            logger.info(f"✅ Uploaded to MinIO: {s3_path}")
            return s3_path

        except S3Error as e:
            logger.error(f"MinIO upload failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to upload file: {str(e)}"
            ) from e

    async def download_file(self, file_path: str) -> bytes:
        """
        Download file from MinIO.

        Args:
            file_path: S3 path (s3://bucket/path) or object name

        Returns:
            bytes: File content

        Raises:
            HTTPException: 404 if not found, 500 if download fails
        """
        try:
            bucket_name, object_name = self._parse_path(file_path)

            logger.info(f"Downloading file: {object_name}")

            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()

            logger.info(f"✅ Downloaded from MinIO: {object_name} ({len(data)} bytes)")
            return data

        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning(f"File not found: {file_path}")
                raise HTTPException(status_code=404, detail="File not found") from e
            else:
                logger.error(f"MinIO download failed: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to download file: {str(e)}"
                ) from e

    async def download_file_stream(
        self, file_path: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream file from MinIO (for large files).

        Args:
            file_path: S3 path or object name

        Yields:
            bytes: File chunks

        Raises:
            HTTPException: If download fails
        """
        try:
            bucket_name, object_name = self._parse_path(file_path)

            logger.info(f"Streaming file: {object_name}")

            response = self.client.get_object(bucket_name, object_name)

            # Stream in chunks
            chunk_size = 8192  # 8KB chunks
            for chunk in response.stream(chunk_size):
                yield chunk

            response.close()
            response.release_conn()
            logger.info(f"✅ Streamed from MinIO: {object_name}")

        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning(f"File not found: {file_path}")
                raise HTTPException(status_code=404, detail="File not found") from e
            else:
                logger.error(f"MinIO stream failed: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to stream file: {str(e)}"
                ) from e

    async def delete_file(self, file_path: str, silent: bool = False) -> bool:
        """
        Delete file from MinIO.

        Args:
            file_path: S3 path or object name
            silent: If True, don't raise exception on error (for GDPR)

        Returns:
            bool: True if deleted, False if not found or error (when silent=True)

        Raises:
            HTTPException: If deletion fails (when silent=False)
        """
        try:
            bucket_name, object_name = self._parse_path(file_path)

            logger.info(f"Deleting file: {object_name}")

            self.client.remove_object(bucket_name, object_name)
            logger.info(f"✅ Deleted from MinIO: {object_name}")
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.info(f"File already deleted: {file_path}")
                return True  # OK for deletion
            else:
                logger.error(f"MinIO delete failed: {e}")
                if silent:
                    return False
                raise HTTPException(
                    status_code=500, detail=f"Failed to delete file: {str(e)}"
                ) from e
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            if silent:
                return False
            raise

    async def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in MinIO.

        Args:
            file_path: S3 path or object name

        Returns:
            bool: True if exists, False otherwise
        """
        try:
            bucket_name, object_name = self._parse_path(file_path)
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error:
            return False

    async def get_presigned_url(
        self, file_path: str, expiry_seconds: int = 3600
    ) -> str:
        """
        Generate presigned URL for temporary file access.

        Args:
            file_path: S3 path or object name
            expiry_seconds: URL expiration time (default: 1 hour)

        Returns:
            str: Presigned URL

        Raises:
            HTTPException: If URL generation fails
        """
        try:
            bucket_name, object_name = self._parse_path(file_path)

            url = self.client.presigned_get_object(
                bucket_name, object_name, expires=timedelta(seconds=expiry_seconds)
            )

            logger.info(
                f"Generated presigned URL: {object_name} (expires in {expiry_seconds}s)"
            )
            return url

        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to generate download URL"
            ) from e

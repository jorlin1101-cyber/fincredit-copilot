# This project was developed with assistance from AI tools.
"""S3-compatible object storage for MinIO, AWS S3, or Cloudflare R2.

Uses boto3 synchronous client run in a thread-pool executor for async
compatibility. The module exposes a singleton initialised at app startup
via ``init_storage_service()``.
"""

import asyncio
import base64
import hashlib
import logging
import os
from collections.abc import Callable
from functools import partial
from typing import Literal

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from ..core.config import Settings

logger = logging.getLogger(__name__)
_failure_callback: Callable[[], None] | None = None
_failure_loop: asyncio.AbstractEventLoop | None = None


def set_storage_failure_callback(callback: Callable[[], None] | None) -> None:
    """Install the lifecycle-owned recovery signal for runtime S3 failures."""
    global _failure_callback, _failure_loop  # noqa: PLW0603
    _failure_callback = callback
    _failure_loop = asyncio.get_running_loop() if callback is not None else None


def _signal_storage_failure(exc: Exception) -> None:
    # A missing object cannot be recovered by reinitializing the bucket.
    if isinstance(exc, ClientError) and exc.response.get("Error", {}).get("Code") in {
        "NoSuchKey", "NoSuchObject", "404",
    }:
        return
    if _failure_callback is not None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # The lifecycle recovery manager schedules async tasks; a caller
            # outside its event loop cannot safely trigger it.
            return
        if loop is not _failure_loop:
            return
        try:
            _failure_callback()
        except Exception:
            logger.exception("Could not schedule object storage recovery")


class StorageService:
    """Thin wrapper around a boto3 S3 client."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        *,
        upload_checksum: Literal["sha256", "md5"] = "sha256",
        auto_create_bucket: bool = True,
    ):
        self._bucket = bucket
        if upload_checksum not in {"sha256", "md5"}:
            raise ValueError("Unsupported upload checksum algorithm")
        self._upload_checksum = upload_checksum
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=10,
                retries={"total_max_attempts": 2, "mode": "standard"},
                # We supply an explicit integrity header below. Avoid the
                # SDK's optional CRC/trailer encoding on S3-compatible hosts.
                request_checksum_calculation="when_required",
                s3={
                    "addressing_style": "path",
                    "use_accelerate_endpoint": False,
                },
            ),
        )
        self._ensure_bucket(auto_create=auto_create_bucket)

    def _ensure_bucket(self, *, auto_create: bool = True) -> None:
        """Check the bucket; optionally create it for local development."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            # Only a missing bucket should trigger creation. In particular,
            # auth errors and gateway failures are not evidence it is absent.
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchBucket", "NotFound"} or not auto_create:
                raise
            logger.info("Creating S3 bucket: %s", self._bucket)
            self._client.create_bucket(Bucket=self._bucket)

    async def upload_file(
        self,
        file_data: bytes,
        object_key: str,
        content_type: str,
    ) -> str:
        """Upload bytes to S3 and return the object key."""
        loop = asyncio.get_running_loop()
        if self._upload_checksum == "md5":
            # R2 explicitly supports Content-MD5 on PutObject. This is a
            # transport integrity check, not a password or security hash.
            checksum = {"ContentMD5": base64.b64encode(
                hashlib.md5(file_data, usedforsecurity=False).digest()
            ).decode("ascii")}
        else:
            checksum = {"ChecksumSHA256": base64.b64encode(
                hashlib.sha256(file_data).digest()
            ).decode("ascii")}
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self._client.put_object,
                    Bucket=self._bucket,
                    Key=object_key,
                    Body=file_data,
                    ContentType=content_type,
                    **checksum,
                ),
            )
        except (BotoCoreError, ClientError) as exc:
            _signal_storage_failure(exc)
            raise
        return object_key

    async def download_file(self, object_key: str) -> bytes:
        """Download file bytes from S3."""
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(self._client.get_object, Bucket=self._bucket, Key=object_key),
            )
            return response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            _signal_storage_failure(exc)
            raise

    async def get_download_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Return a presigned GET URL for the given object key."""
        loop = asyncio.get_running_loop()
        url: str = await loop.run_in_executor(
            None,
            partial(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self._bucket, "Key": object_key},
                ExpiresIn=expires_in,
            ),
        )
        return url

    @staticmethod
    def build_object_key(application_id: int, document_id: int, filename: str) -> str:
        """Build the S3 object key: {application_id}/{document_id}/{filename}.

        Strips path components from filename to prevent path traversal attacks.
        """
        safe_name = os.path.basename(filename) or f"doc-{document_id}"
        return f"{application_id}/{document_id}/{safe_name}"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: StorageService | None = None


class StorageUnavailableError(RuntimeError):
    """Object storage could not be initialized."""


def _create_storage_service(cfg: Settings) -> StorageService:
    return StorageService(
        endpoint=cfg.S3_ENDPOINT,
        access_key=cfg.S3_ACCESS_KEY,
        secret_key=cfg.S3_SECRET_KEY,
        bucket=cfg.S3_BUCKET,
        region=cfg.S3_REGION,
        upload_checksum=cfg.S3_UPLOAD_CHECKSUM,
        auto_create_bucket=cfg.S3_AUTO_CREATE_BUCKET,
    )


def init_storage_service(cfg: Settings) -> StorageService:
    """Initialise the singleton synchronously for non-async callers."""
    global _service  # noqa: PLW0603
    _service = _create_storage_service(cfg)
    logger.info("StorageService initialised (bucket=%s)", cfg.S3_BUCKET)
    return _service


async def async_init_storage_service(cfg: Settings) -> StorageService:
    """Connect off the event loop and publish only after successful completion.

    If cancelled, the worker thread may finish later but cannot publish a
    singleton into a shutting-down application.
    """
    global _service  # noqa: PLW0603
    service = await asyncio.to_thread(_create_storage_service, cfg)
    _service = service
    logger.info("StorageService initialised (bucket=%s)", cfg.S3_BUCKET)
    return service


def get_storage_service() -> StorageService:
    """Return the initialised StorageService singleton."""
    if _service is None:
        exc = StorageUnavailableError("StorageService not initialised -- call init_storage_service() first")
        _signal_storage_failure(exc)
        raise exc
    return _service


def is_storage_initialized() -> bool:
    """Report only in-process initialization state, without contacting S3."""
    return _service is not None

"""S3 upload request integrity checks without contacting external services."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from botocore.awsrequest import AWSResponse
from botocore.exceptions import ClientError
from pydantic import ValidationError

from src.core.config import Settings
from src.services.storage import StorageService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_data", "checksum"),
    [
        (b"abc", "ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0="),
        (b"", "47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU="),
    ],
)
async def test_upload_sends_sha256_checksum_matching_file_data(file_data, checksum):
    """Known SHA-256 vectors protect the body/checksum contract at the S3 boundary."""
    with patch("src.services.storage.boto3.client") as create_client:
        service = StorageService(
            endpoint="https://storage.example.test",
            access_key="test-access",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        result = await service.upload_file(
            file_data, "checks/probe.bin", "application/octet-stream"
        )

    assert result == "checks/probe.bin"
    create_client.return_value.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="checks/probe.bin",
        Body=file_data,
        ContentType="application/octet-stream",
        ChecksumSHA256=checksum,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_data", "checksum"),
    [(b"abc", "kAFQmDzST7DWlj99KOF/cg=="), (b"", "1B2M2Y8AsgTpgAmY7PhCfg==")],
)
async def test_r2_upload_serializes_supported_integrity_header_without_trailers(file_data, checksum):
    """Inspect the real botocore HTTP request, without making a network call."""
    captured = {}

    def capture_request(request, **_kwargs):
        captured["headers"] = {
            key.lower(): value.decode("ascii") if isinstance(value, bytes) else value
            for key, value in request.headers.items()
        }
        captured["body"] = request.body.read() if hasattr(request.body, "read") else request.body
        return AWSResponse(request.url, 200, {"ETag": '"test-etag"'}, SimpleNamespace(stream=lambda: iter([b""])))

    with patch.object(StorageService, "_ensure_bucket"):
        service = StorageService(
            endpoint="https://account.r2.cloudflarestorage.com",
            access_key="test-access",
            secret_key="test-secret",
            bucket="documents",
            region="auto",
            upload_checksum="md5",
            auto_create_bucket=False,
        )
    service._client.meta.events.register("before-send.s3.PutObject", capture_request)
    try:
        await service.upload_file(file_data, "probe/test.bin", "application/octet-stream")
    finally:
        service._client.close()

    assert captured["body"] == file_data
    headers = captured["headers"]
    assert headers["content-md5"] == checksum
    assert headers["content-length"] == str(len(file_data))
    assert "aws-chunked" not in headers.get("content-encoding", "")
    assert "x-amz-trailer" not in headers
    assert "x-amz-checksum-sha256" not in headers
    assert "x-amz-checksum-crc32" not in headers
    assert "x-amz-sdk-checksum-algorithm" not in headers


@pytest.mark.parametrize("code", ["404", "NoSuchBucket", "403"])
def test_precreated_bucket_never_requires_bucket_creation_permission(code):
    failure = ClientError({"Error": {"Code": code}}, "HeadBucket")
    with patch("src.services.storage.boto3.client") as create_client:
        create_client.return_value.head_bucket.side_effect = failure
        with pytest.raises(ClientError) as error:
            StorageService(
                endpoint="https://account.r2.cloudflarestorage.com",
                access_key="test-access",
                secret_key="test-secret",
                bucket="documents",
                region="auto",
                upload_checksum="md5",
                auto_create_bucket=False,
            )
        assert error.value is failure
        create_client.return_value.create_bucket.assert_not_called()


def test_r2_settings_parse_false_and_reject_unknown_checksum(monkeypatch):
    monkeypatch.setenv("S3_AUTO_CREATE_BUCKET", "false")
    monkeypatch.setenv("S3_UPLOAD_CHECKSUM", "md5")
    cfg = Settings(_env_file=None)
    assert cfg.S3_AUTO_CREATE_BUCKET is False
    assert cfg.S3_UPLOAD_CHECKSUM == "md5"
    monkeypatch.setenv("S3_UPLOAD_CHECKSUM", "typo")
    with pytest.raises(ValidationError, match="S3_UPLOAD_CHECKSUM"):
        Settings(_env_file=None)

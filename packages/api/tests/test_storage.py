"""S3 upload request integrity checks without contacting external services."""

from unittest.mock import patch

import pytest

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

# FinCredit demo object storage

This container builds unmodified MinIO community source from the official repository.
It does not depend on the retired Docker Hub or Quay MinIO images.

- Upstream release: https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z
- Source commit: `9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a`
- Source archive SHA-256: `45521908307306e925c98d629e1c17d78c8b72b6ee242b1bfb1409f7d8ee5841`
- Official Go and Alpine base images are pinned by digest; source downloads are checksum verified.
- The upstream AGPL license is preserved at `/usr/share/licenses/minio/LICENSE`.

Build from the repository root with `docker build -f packages/storage/Containerfile -t fincredit-storage .`.
The build verifies the executable with `minio --version` in both stages. Configure
`MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` only as runtime secrets, never build arguments.
The service listens on port 10000; its health path is `/minio/health/live`.

`/tmp/fincredit-data` is ephemeral demo storage and is lost when the container is replaced.
The upstream community repository is archived. This is a reproducible compatibility
recovery image, not a claim of ongoing upstream maintenance.

Prepared on 2026-10-10. Source checksum and public base-image manifests were checked.
Local container execution was not performed because the Docker Linux daemon was unavailable;
a successful build and service health check are still required before using this image.

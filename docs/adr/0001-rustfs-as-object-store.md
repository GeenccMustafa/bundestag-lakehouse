# 0001. RustFS as the local S3-compatible object store
Date: 2026-10-25 · Status: accepted

## Context
The Bronze layer needs an S3-compatible object store that runs locally in Docker Compose, so the
same ingestion code can later target real S3 or a cloud lakehouse. The original plan was MinIO,
but the MinIO community edition is no longer maintained: the `minio/minio` GitHub repository is
archived (last release `RELEASE.2025-10-15`) and the `minio/minio` image is no longer on Docker Hub.

## Decision
Use **RustFS** (`rustfs/rustfs`, Apache-2.0), pinned to a released version, as the local object store.

## Alternatives considered
- **MinIO (last available release)** — familiar and well documented, but unmaintained: no security
  fixes, and the image is no longer published on Docker Hub.
- **SeaweedFS** — most mature and widely used, Apache-2.0; but several components
  (master/volume/filer/s3 gateway), so more setup for a single-node dev stack.
- **Garage** — lightweight and actively developed; AGPL-3.0, needs manual cluster-layout and key
  bootstrap steps, no web console.

## Consequences
- Easy: MinIO-style single container with a web console; code only talks the S3 API
  (boto3 / DuckDB `httpfs`), so swapping the store later only changes an endpoint URL.
- Hard: RustFS is younger (1.0 in 2026); if we hit S3-compatibility gaps, revisit with SeaweedFS.
- We must keep the image tag pinned and bump it deliberately (Dependabot watches Docker images).

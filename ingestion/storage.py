"""Object storage for the Bronze layer: S3 (RustFS locally) or in-memory for tests.

Ingestion code depends only on the `ObjectStore` protocol, so the same extraction logic runs
against RustFS, real S3, or a dict in unit tests.
"""

from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class ObjectStore(Protocol):
    """Minimal key/value interface over a bucket. Keys are ``/``-separated paths."""

    def put(self, key: str, body: bytes, content_type: str = "application/json") -> None:
        """Write `body` to `key`, replacing any existing object."""
        ...

    def get(self, key: str) -> bytes | None:
        """Return the object at `key`, or None if it does not exist."""
        ...

    def list(self, prefix: str) -> list[str]:
        """Return all keys starting with `prefix`, sorted."""
        ...

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object under `prefix` and return how many were deleted."""
        ...


class S3ObjectStore:
    """`ObjectStore` backed by an S3-compatible service such as RustFS.

    Uses path-style addressing (``http://host:9000/<bucket>/<key>``), which RustFS and most
    self-hosted S3 implementations expect.

    Args:
        bucket: Bucket to read from and write to.
        endpoint_url: S3 endpoint, e.g. ``http://localhost:9000``.
        access_key: S3 access key id.
        secret_key: S3 secret access key.
    """

    def __init__(self, bucket: str, endpoint_url: str, access_key: str, secret_key: str) -> None:
        self.bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(s3={"addressing_style": "path"}, retries={"mode": "standard"}),
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if it does not exist yet."""
        try:
            self._s3.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._s3.create_bucket(Bucket=self.bucket)

    def put(self, key: str, body: bytes, content_type: str = "application/json") -> None:
        """Write `body` to `key`, replacing any existing object."""
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)

    def get(self, key: str) -> bytes | None:
        """Return the object at `key`, or None if it does not exist.

        Raises:
            botocore.exceptions.ClientError: For any error other than a missing key.
        """
        try:
            return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                return None
            raise

    def list(self, prefix: str) -> list[str]:
        """Return all keys starting with `prefix`, sorted (follows S3 pagination)."""
        keys: list[str] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return sorted(keys)

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object under `prefix`, in batches of 1,000 (the S3 limit).

        Returns:
            Number of deleted objects.
        """
        keys = self.list(prefix)
        for start in range(0, len(keys), 1000):
            batch = [{"Key": k} for k in keys[start : start + 1000]]
            self._s3.delete_objects(Bucket=self.bucket, Delete={"Objects": batch})
        return len(keys)


class InMemoryObjectStore:
    """`ObjectStore` kept in a dict, for unit tests.

    Attributes:
        objects: Stored objects by key; tests may inspect it directly.
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, body: bytes, content_type: str = "application/json") -> None:
        """Store `body` under `key`; `content_type` is ignored."""
        self.objects[key] = body

    def get(self, key: str) -> bytes | None:
        """Return the object at `key`, or None if it does not exist."""
        return self.objects.get(key)

    def list(self, prefix: str) -> list[str]:
        """Return all keys starting with `prefix`, sorted."""
        return sorted(k for k in self.objects if k.startswith(prefix))

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object under `prefix` and return how many were deleted."""
        keys = self.list(prefix)
        for k in keys:
            del self.objects[k]
        return len(keys)

"""Runtime settings, read from environment variables only.

Nothing secret has a default: a missing API key or storage credential raises
`MissingSettingError` instead of silently falling back to a well-known value.
"""

import os
from dataclasses import dataclass


class MissingSettingError(RuntimeError):
    """A required environment variable is unset or empty."""


def _required(name: str) -> str:
    """Return the stripped value of `name`, or raise if it is unset or blank."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingSettingError(f"Environment variable {name} is not set (see .env.example)")
    return value


def _required_any(*names: str) -> str:
    """Return the first non-blank value among `names`, or raise if none is set."""
    for name in names:
        if value := os.environ.get(name, "").strip():
            return value
    raise MissingSettingError(f"None of {', '.join(names)} is set (see .env.example)")


@dataclass(frozen=True)
class Settings:
    """Connection settings for the DIP API and the Bronze object store.

    Attributes:
        dip_api_key: DIP API key, sent in the `Authorization` header.
        s3_endpoint_url: S3 endpoint of the object store, e.g. ``http://localhost:9000``.
        s3_access_key: S3 access key id.
        s3_secret_key: S3 secret access key.
        bucket: Bucket that holds the lakehouse (`bronze/`, `silver/`, `state/` ...).
        dip_base_url: Base URL of the DIP API, without a trailing slash.
    """

    dip_api_key: str
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    bucket: str = "lakehouse"
    dip_base_url: str = "https://search.dip.bundestag.de/api/v1"

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the environment.

        Inside Docker Compose the ``S3_*`` variables are set. On the host,
        ``uv run --env-file .env`` provides the ``RUSTFS_*`` credentials instead, and the
        endpoint defaults to RustFS on localhost.

        Environment variables:
            DIP_API_KEY: Required.
            S3_ACCESS_KEY / RUSTFS_ACCESS_KEY: Required, first one set wins.
            S3_SECRET_KEY / RUSTFS_SECRET_KEY: Required, first one set wins.
            S3_ENDPOINT_URL: Optional, defaults to ``http://localhost:9000``.
            LAKEHOUSE_BUCKET: Optional, defaults to ``lakehouse``.

        Returns:
            The populated settings.

        Raises:
            MissingSettingError: If a required variable is unset or blank.
        """
        return cls(
            dip_api_key=_required("DIP_API_KEY"),
            s3_endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
            s3_access_key=_required_any("S3_ACCESS_KEY", "RUSTFS_ACCESS_KEY"),
            s3_secret_key=_required_any("S3_SECRET_KEY", "RUSTFS_SECRET_KEY"),
            bucket=os.environ.get("LAKEHOUSE_BUCKET", "lakehouse"),
        )

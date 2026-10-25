"""Runtime settings, read from environment variables only."""

import os
from dataclasses import dataclass


class MissingSettingError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingSettingError(f"Environment variable {name} is not set (see .env.example)")
    return value


@dataclass(frozen=True)
class Settings:
    dip_api_key: str
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    bucket: str = "lakehouse"
    dip_base_url: str = "https://search.dip.bundestag.de/api/v1"

    @classmethod
    def from_env(cls) -> "Settings":
        """Inside Compose the S3_* variables are set; on the host, `uv run --env-file .env`
        provides the RUSTFS_* ones and the endpoint defaults to the localhost port."""
        return cls(
            dip_api_key=_required("DIP_API_KEY"),
            s3_endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
            s3_access_key=_required_any("S3_ACCESS_KEY", "RUSTFS_ACCESS_KEY"),
            s3_secret_key=_required_any("S3_SECRET_KEY", "RUSTFS_SECRET_KEY"),
            bucket=os.environ.get("LAKEHOUSE_BUCKET", "lakehouse"),
        )


def _required_any(*names: str) -> str:
    for name in names:
        if value := os.environ.get(name, "").strip():
            return value
    raise MissingSettingError(f"None of {', '.join(names)} is set (see .env.example)")

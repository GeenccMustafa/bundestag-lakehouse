"""Browse the lakehouse in the DuckDB UI at http://localhost:4213.

    uv run --env-file .env python scripts/duckdb_ui.py

Attaches the DuckLake catalog `lake` read-only (metadata in Postgres, data as Parquet in
RustFS). Nothing is locked on disk, so `dbt build` can run while the UI is open; a query
sees the latest snapshot committed when it starts.
"""

import contextlib
import os
import signal
import sys

import duckdb


def _env(*names: str, default: str | None = None) -> str:
    for name in names:
        if value := os.environ.get(name, "").strip():
            return value
    if default is not None:
        return default
    sys.exit(f"None of {', '.join(names)} is set; run with `uv run --env-file .env ...`")


def main() -> None:
    # In-memory main connection: the UI keeps its notebooks there.
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL ducklake; INSTALL postgres;")

    # Session-only secrets: S3 for Parquet files and the bronze.* views, Postgres for the
    # DuckLake catalog (default-named so the attach below picks it up).
    con.execute(
        "CREATE SECRET (TYPE s3, KEY_ID ?, SECRET ?, ENDPOINT ?, URL_STYLE 'path', "
        "USE_SSL false, REGION 'us-east-1')",
        [
            _env("S3_ACCESS_KEY", "RUSTFS_ACCESS_KEY"),
            _env("S3_SECRET_KEY", "RUSTFS_SECRET_KEY"),
            _env("S3_ENDPOINT", default="localhost:9000"),
        ],
    )
    con.execute(
        "CREATE SECRET (TYPE postgres, HOST ?, PORT ?, DATABASE ?, USER ?, PASSWORD ?)",
        [
            _env("DUCKLAKE_PG_HOST", default="localhost"),
            _env("DUCKLAKE_PG_PORT", default="5433"),
            _env("DUCKLAKE_PG_DB", default="ducklake"),
            _env("DUCKLAKE_PG_USER", default="ducklake"),
            _env("DUCKLAKE_PG_PASSWORD"),
        ],
    )
    con.execute("ATTACH 'ducklake:postgres:' AS lake (READ_ONLY)")
    con.execute("USE lake")

    con.execute("INSTALL ui; LOAD ui;")
    (message,) = con.execute("CALL start_ui_server()").fetchone()
    print(f"{message}  (Ctrl+C to stop)", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        signal.pause()


if __name__ == "__main__":
    main()

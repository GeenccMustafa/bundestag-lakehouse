"""Browse the lakehouse in the DuckDB UI at http://localhost:4213.

    uv run --env-file .env python scripts/duckdb_ui.py

The lakehouse file is attached read-only, so nothing here can change Silver or Gold. The
attach still holds a file lock: stop this (Ctrl+C) before running `dbt build`.
"""

import contextlib
import os
import signal
import sys

import duckdb

DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "data/lakehouse.duckdb")


def _env(*names: str) -> str:
    for name in names:
        if value := os.environ.get(name, "").strip():
            return value
    sys.exit(f"None of {', '.join(names)} is set; run with `uv run --env-file .env ...`")


def main() -> None:
    if not os.path.exists(DUCKDB_PATH):
        sys.exit(f"{DUCKDB_PATH} not found; run `dbt build` first")

    # The main connection is in-memory (writable) because the UI stores its notebooks there;
    # the lakehouse itself is attached read-only.
    con = duckdb.connect()
    con.execute(f"ATTACH '{DUCKDB_PATH}' AS lakehouse (READ_ONLY)")
    con.execute("USE lakehouse")

    # Session-only S3 secret so the bronze.* views, which read RustFS, work in the UI too.
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(
        "CREATE SECRET (TYPE s3, KEY_ID ?, SECRET ?, ENDPOINT ?, URL_STYLE 'path', "
        "USE_SSL false, REGION 'us-east-1')",
        [
            _env("S3_ACCESS_KEY", "RUSTFS_ACCESS_KEY"),
            _env("S3_SECRET_KEY", "RUSTFS_SECRET_KEY"),
            os.environ.get("S3_ENDPOINT", "localhost:9000"),
        ],
    )

    con.execute("INSTALL ui; LOAD ui;")
    (message,) = con.execute("CALL start_ui_server()").fetchone()
    print(f"{message}  (Ctrl+C to stop)", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        signal.pause()


if __name__ == "__main__":
    main()

"""Open a read-only DuckDB connection to the lakehouse.

Two targets, mirroring dbt's profiles (dbt/profiles.yml):

- ``dev`` (default): the real lake. DuckLake catalog in Postgres, Parquet in RustFS. Needs
  ``docker compose up -d postgres rustfs`` and the credentials from ``.env``.
- ``ci``: the lake ``dbt build --target ci`` writes from the sample data, a local DuckLake
  catalog file under ``DBT_CI_DIR``. Needs no services.

The target is chosen with ``LAKE_TARGET``. Attaching ``READ_ONLY`` means the dashboard can
never change the lake, and since DuckLake keeps no lock on disk, dbt can write while the
dashboard is open; every query sees the latest snapshot committed when it starts.
"""

import os

import duckdb

TARGETS = ("dev", "ci")


class LakeConfigError(RuntimeError):
    """The environment does not describe a reachable lake (unknown target, missing secret)."""


def _env(*names: str, default: str | None = None) -> str:
    """Return the first non-blank variable among `names`, else `default`.

    Raises:
        LakeConfigError: None is set and there is no default.
    """
    for name in names:
        if value := os.environ.get(name, "").strip():
            return value
    if default is not None:
        return default
    raise LakeConfigError(f"None of {', '.join(names)} is set; run with `uv run --env-file .env`")


def connect(target: str | None = None) -> duckdb.DuckDBPyConnection:
    """Connect to the lakehouse and attach it read-only as catalog ``lake``.

    The returned connection is in-memory apart from the attached catalog; secrets live only in
    this session. DuckDB connections are not thread-safe, so concurrent callers should each use
    ``connection.cursor()``.

    Args:
        target: ``"dev"`` or ``"ci"``; defaults to ``LAKE_TARGET`` or ``"dev"``.

    Returns:
        A connection on which ``lake.gold.*`` resolves to the Gold tables.

    Raises:
        LakeConfigError: Unknown target or missing credentials.
        duckdb.Error: The catalog or the object store is unreachable.
    """
    target = target or os.environ.get("LAKE_TARGET", "dev")
    if target not in TARGETS:
        raise LakeConfigError(f"LAKE_TARGET must be one of {TARGETS}, got {target!r}")

    con = duckdb.connect()
    if target == "ci":
        ci_dir = _env("DBT_CI_DIR", default="/tmp/bundestag-dbt-ci")  # noqa: S108 - dbt's default
        con.execute("INSTALL ducklake")
        con.execute(f"ATTACH 'ducklake:{ci_dir}/catalog.ducklake' AS lake (READ_ONLY)")
        return con

    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL ducklake; INSTALL postgres;")
    con.execute(
        "CREATE SECRET (TYPE s3, KEY_ID ?, SECRET ?, ENDPOINT ?, URL_STYLE 'path', "
        "USE_SSL false, REGION 'us-east-1')",
        [
            _env("S3_ACCESS_KEY", "RUSTFS_ACCESS_KEY"),
            _env("S3_SECRET_KEY", "RUSTFS_SECRET_KEY"),
            _env("S3_ENDPOINT", default="localhost:9000"),
        ],
    )
    # The default-named postgres secret is picked up by the attach, so the password never
    # appears in the ATTACH statement.
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
    return con

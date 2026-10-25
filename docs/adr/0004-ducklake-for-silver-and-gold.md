# 0004. DuckLake for Silver and Gold (Parquet in RustFS, catalog in Postgres)
Date: 2026-10-25 · Status: accepted · Supersedes the storage part of [0003](0003-silver-with-dbt-duckdb.md)

## Context
Silver lived in a local DuckDB file (`data/lakehouse.duckdb`). Two problems showed up quickly:
only one process can open the file for writing — the DuckDB UI blocked `dbt build` — and the
file is tied to one machine, while Airflow (Phase 4) and the dashboard (Phase 5) run elsewhere.
It also wasn't a lakehouse: only Bronze lived in object storage.

## Decision
Store Silver and Gold as **DuckLake** tables:
- **Data** as Parquet in RustFS: `s3://lakehouse/<schema>/<table>/ducklake-*.parquet`.
- **Catalog** (tables, columns, files, snapshots) in the existing Postgres, in its own database
  `ducklake` with its own role, created idempotently by the `postgres-init` Compose service.
  Postgres is published on `127.0.0.1:5433` for host-side dbt and DuckDB.
- dbt runs DuckDB **in memory** and attaches the catalog as `lake` (`profiles.yml`). The
  catalog password comes from a Postgres secret named `__default_postgres` (dbt-duckdb names
  secrets `_dbt_secret_N`, which the postgres extension does not pick up on its own).
- `DATA_INLINING_ROW_LIMIT 0`: always write Parquet, even for small tables.
- A project materialization **`ducklake_table`** builds tables with one atomic
  `CREATE OR REPLACE TABLE`. dbt's `table` materialization creates `<name>__dbt_tmp` and renames
  it, and DuckLake keeps files in the folder named at creation, so every table would have lived
  under `…/<name>__dbt_tmp/`.
- `dbt run-operation ducklake_maintenance` expires old snapshots and deletes unreferenced files.

## Alternatives considered
- **Keep the DuckDB file** — simplest, but single writer, single machine, no time travel.
- **Plain Parquet via dbt-duckdb `external` materialization** — open files in S3, but no
  catalog, no transactions (readers can see half-written tables), no snapshots.
- **Delta Lake / Iceberg locally** — the industry formats, but DuckDB's write support for them is
  limited and they need more moving parts; Delta Lake comes in Phase 6 on Databricks, and
  comparing it with DuckLake is part of that phase.
- **SQLite or a DuckDB file as DuckLake catalog** — no extra service, but weaker multi-client
  behaviour; Postgres is already running.

## Consequences
- dbt, the DuckDB UI and later the dashboard read and write concurrently (verified: 40/40 reads
  succeeded while `dbt build` rewrote Silver).
- Time travel: `select … from lake.silver.t at (version => N)`.
- Every build adds files and snapshots; housekeeping must run regularly (Phase 4 schedules it).
- Postgres is now part of the data platform, not only Airflow's backend: back it up with the
  bucket, or the Parquet files lose their table definitions.

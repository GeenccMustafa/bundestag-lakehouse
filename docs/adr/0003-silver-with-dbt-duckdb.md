# 0003. Silver layer: dbt + DuckDB reading Bronze directly from S3
Date: 2026-10-25 · Status: accepted; storage part superseded by [0004](0004-ducklake-for-silver-and-gold.md)

## Context
Bronze holds raw API pages (`{"numFound", "cursor", "documents": [...]}`) as JSON files in
RustFS. Silver must be typed, flattened and deduplicated, with tests and documentation, and must
be rebuildable from Bronze alone. The DIP schema is nested and sparse: many fields appear only on
some records, and records are re-delivered whenever they change.

## Decision
- **dbt-duckdb** with a local DuckDB file (`data/lakehouse.duckdb`). The `dip` source uses
  dbt-duckdb's `external_location` to read Bronze with
  `read_json_objects(..., format='unstructured', hive_partitioning=true, filename=true)`:
  one JSON value per file, plus `dt`, `run` and `filename` columns.
- **Explicit extraction instead of schema inference.** Documents are unnested as `JSON` and
  every field is extracted and cast by name (`doc ->> 'titel'`). A new or missing field in the
  API never breaks the read; it only shows up as NULL or is ignored until we model it.
- **Two layers inside dbt:** `bronze.base_dip__*` views (every version, typed) and
  `silver.stg_dip__*` tables (latest version per id: newest `aktualisiert`, ties broken by the
  newest Bronze file). Nested arrays become child tables (`stg_dip__drucksache__ressort`, …).
- Relationship tests towards entities we don't hold completely yet are **warnings**, not errors.

## Alternatives considered
- **`read_json` with auto-detected structs** — fewer lines, but inferred types change with the
  sample and break on sparse nested fields.
- **Flattening in Python during ingestion** — would make Bronze no longer raw (ETL instead of
  ELT) and lose replayability.
- **Writing Silver as Parquet back to S3** (dbt-duckdb `external` materialization) — closer to a
  "real" lakehouse; deferred until Phase 6 compares against Delta Lake. The DuckDB file is
  simpler to query from the dashboard for now.

## Consequences
- `dbt build --full-refresh` recreates Silver from Bronze at any time.
- Bronze views need S3 credentials in the session that queries them (the dbt profile provides
  them; ad-hoc DuckDB sessions must create a secret).
- Every staging model lists its columns explicitly — more SQL, but the contract is visible.

# 0002. Bronze layout, run-scoped overwrites and watermarks
Date: 2026-10-25 · Status: accepted

## Context
Ingestion must be incremental (only fetch what changed) and idempotent (re-running a run must
not duplicate or corrupt data). DIP records are updated after publication, so the same id can
legitimately arrive many times. Bronze must stay a faithful replay log of what the API returned.

## Decision
- **Layout:** `bronze/<entity>/dt=<YYYY-MM-DD>/run=<run_id>/page=NNNN.json` holds each API
  response byte-exact; `_SUCCESS.json` (written last) is the run manifest: window, page log,
  counts, max `aktualisiert`. Hive-style `key=value` folders let DuckDB expose `dt` and `run`
  as columns.
- **Run id = time window** (`<start>_<end>` in UTC). The same window always maps to the same
  prefix; a run deletes its own prefix before writing, so a retry replaces, never appends.
- **Window, not "since last run":** Airflow runs use their data interval (+1h overlap). The
  CLI's incremental mode starts from the stored **watermark** (max `aktualisiert` of
  successful runs, minus 1h). Watermarks only move forward and only after the manifest exists.
- **Duplicates are expected** (overlap, updated records) and are removed in Silver by keeping
  the latest `aktualisiert` per id.

## Alternatives considered
- **Append-only with random file names** — simplest, but retries duplicate data and a
  half-failed run leaves partial output that looks complete.
- **Wrapping each response in a metadata envelope** — self-describing files, but no longer
  byte-exact; metadata lives in the manifest instead.
- **Watermark-driven Airflow runs** — fewer overlaps, but a run's output would depend on when
  it ran, breaking idempotent retries and backfills.

## Consequences
- Retries, clears and backfills are safe to repeat.
- Silver must deduplicate; readers may ignore runs without `_SUCCESS.json`.
- Changing the run-id scheme later would orphan old prefixes — treat it as a breaking change.

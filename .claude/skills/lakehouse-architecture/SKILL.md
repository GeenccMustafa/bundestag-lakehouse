---
name: lakehouse-architecture
description: Layer contracts, naming and folder conventions for this Bronze → Silver → Gold lakehouse, plus how to record design decisions as ADRs. Use when adding a new data source, table, dbt model, storage path or service; when deciding which layer some logic belongs in; or when a change alters the architecture (new tool, new storage format, new dependency between layers).
---

# Lakehouse Architecture

The project's architecture rules. Read this before placing new logic, data or services.

## Layer contracts

| Layer | Where | Format | Who writes it | Contract |
|-------|-------|--------|---------------|----------|
| **Bronze** | MinIO `s3://lakehouse/bronze/<entity>/dt=YYYY-MM-DD/` | Raw JSON (one file per API page, as received) | `ingestion/` (Python) | Append-only and immutable. No parsing, no renaming, no filtering. Every file can be traced back to one API request. |
| **Silver** | dbt `models/staging/` (+ `intermediate/`) | DuckDB / Parquet | dbt | One model per source entity. Flattened, typed, renamed to snake_case, deduplicated to the **latest version per id** (by `aktualisiert`). No business logic or joins across entities in staging. |
| **Gold** | dbt `models/marts/` | DuckDB / Parquet | dbt | Kimball star schema (`fct_*`, `dim_*`). Every model has a declared grain. See the `dimensional-modeling` skill. |
| **Serving** | `dashboard/` | — | Streamlit | Reads **Gold only**. Never queries Bronze or Silver. |

Rules that follow from this:

- **Data flows one way**: Bronze → Silver → Gold → Serving. Nothing reads from a layer to its right.
- **Bronze is the replay log.** Any Silver/Gold table must be rebuildable from Bronze alone (`dbt build --full-refresh`). Never fix data by editing Bronze files; fix the transformation.
- **Ingestion does not transform.** If you're tempted to clean data in Python, put it in a staging model instead (ELT, not ETL).
- **Idempotency everywhere**: re-running any task for the same logical date must produce the same result (overwrite the partition, `merge`/`delete+insert` incremental strategies, deterministic file names).

## Naming

- dbt: `stg_dip__<entity>` (staging), `int_<entity>__<verb>` (intermediate), `fct_<event_plural>`, `dim_<noun>` (marts), snapshots `snp_<entity>`.
- Columns: snake_case; keys `<entity>_id` (natural) and `<entity>_key` (surrogate); timestamps `*_at` (UTC), dates `*_date`; booleans `is_*` / `has_*`.
- Bronze objects: `bronze/<entity>/dt=<run_date>/<run_id>_page=<nnnn>.json`. Watermarks: `state/watermarks/<entity>.json`.
- Python modules: `ingestion/<concern>.py` (e.g. `client.py`, `storage.py`, `watermark.py`).

## Where does this logic go?

```
Is it about talking to the API (auth, paging, retry)?      → ingestion/client
Is it about where/how raw bytes are stored?                 → ingestion/storage
Is it parsing, typing, renaming, dedup of ONE entity?       → dbt staging
Is it combining entities or reshaping for reuse?            → dbt intermediate
Is it a business fact/dimension someone will query?         → dbt marts
Is it "when does what run, in which order"?                 → airflow/dags
Is it presentation only?                                    → dashboard
```

## Architecture Decision Records

Any decision that is hard to reverse or that someone will later ask "why?" about (choosing a tool, storage format, partition scheme, incremental strategy, SCD type) gets an ADR in `docs/adr/NNNN-short-title.md`:

```markdown
# NNNN. <Title>
Date: YYYY-MM-DD · Status: proposed | accepted | superseded by NNNN

## Context
What forces are at play? What problem are we solving?

## Decision
What we chose, stated in one or two sentences.

## Alternatives considered
Each option with its main trade-off.

## Consequences
What becomes easier, what becomes harder, what we must now do.
```

When you propose an architectural change, draft the ADR first and let the user decide before writing code.

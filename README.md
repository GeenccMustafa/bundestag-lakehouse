# Bundestag Open-Data Lakehouse

End-to-end data platform built on the Bundestag's [DIP API](https://dip.bundestag.de/über-dip/hilfe/api):
raw data lands in a **Bronze** layer, is cleaned in **Silver** and modeled into a **Gold** star schema,
kept up to date by an orchestrated pipeline.

```
DIP API ──► [Ingestion: Python] ──► BRONZE (RustFS/S3, raw JSON, date-partitioned)
                                        │
                              [dbt + DuckDB]
                                        ▼
                                  SILVER (cleaned, typed, deduplicated)
                                        ▼
                                  GOLD (star schema: facts + dimensions)
                                        ▼
                              Dashboard (Streamlit) + dbt docs

Orchestration: Airflow (+ Cosmos)   ·   CI/CD: GitHub Actions
```

**Stack:** Python 3.12, uv, Docker Compose, RustFS (S3), Airflow, dbt-core, dbt-duckdb, DuckDB, Parquet — later Databricks Free Edition & Delta Lake.

## Getting started

```bash
uv sync                          # Python env + dev tools
uv run pre-commit install        # run hooks on every commit
cp .env.example .env             # then replace every change-me value
docker compose up -d             # RustFS :9001, Airflow :8080 (localhost only)
```

Load data into Bronze (RustFS bucket `lakehouse`):

```bash
uv run --env-file .env python -m ingestion backfill --days 7   # one idempotent run per day
uv run --env-file .env python -m ingestion extract              # incremental from watermarks
uv run --env-file .env python -m ingestion status
```

In Airflow, the `dip_ingestion` DAG runs daily, one task per DIP entity.

Design decisions are recorded in [`docs/adr/`](docs/adr/).

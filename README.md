# Bundestag Open-Data Lakehouse

End-to-end data platform built on the Bundestag's [DIP API](https://dip.bundestag.de/über-dip/hilfe/api):
raw data lands in a **Bronze** layer, is cleaned in **Silver** and modeled into a **Gold** star schema,
kept up to date by an orchestrated pipeline.

```
DIP API ──► [Ingestion: Python] ──► BRONZE (MinIO/S3, raw JSON, date-partitioned)
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

**Stack:** Python 3.12, uv, Docker Compose, MinIO, Airflow, dbt-core, dbt-duckdb, DuckDB, Parquet — later Databricks Free Edition & Delta Lake.

## Roadmap

- [ ] Phase 0 — Infrastructure (repo, uv, ruff, pre-commit, Docker Compose, CI)
- [ ] Phase 1 — Ingestion & Bronze (API client, incremental + idempotent loads, Airflow DAG)
- [ ] Phase 2 — Silver (dbt staging models, tests, source freshness)
- [ ] Phase 3 — Gold (Kimball star schema, incremental models, SCD2 snapshots)
- [ ] Phase 4 — Orchestration & CI/CD (Cosmos, end-to-end DAG, slim CI, dbt docs on Pages)
- [ ] Phase 5 — Presentation (Streamlit dashboard)
- [ ] Phase 6 — Databricks migration (Delta Lake, Unity Catalog, Workflows)

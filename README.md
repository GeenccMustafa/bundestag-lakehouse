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

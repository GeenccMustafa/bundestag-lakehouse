# Bundestag Open-Data Lakehouse

An end-to-end data platform on the open data of the German Bundestag. It pulls parliamentary
documents, procedures, activities and members from the official
[DIP API](https://dip.bundestag.de/über-dip/hilfe/api), lands them untouched in a **Bronze**
layer, cleans them into **Silver** tables and models them into a **Gold** star schema —
incrementally, idempotently, tested and orchestrated.

It answers questions like *which ministry produces the most printed papers*, *how long does a
bill take from first reading to promulgation* or *how active is each member of parliament*.

## Architecture

```mermaid
flowchart LR
    api(["DIP API<br/>Bundestag"])

    subgraph ingest["Ingestion · Python"]
        client["client.py<br/>cursor paging, retries"]
        extract["extract.py<br/>windows + watermarks"]
    end

    subgraph lake["Object storage · RustFS (S3) · bucket lakehouse"]
        bronze[("bronze/<br/>raw JSON pages")]
        silver[("silver/<br/>Parquet · DuckLake")]
        gold[("gold/<br/>Parquet · DuckLake")]
    end

    dbt["dbt + DuckDB<br/>transform + test"]
    catalog[("Postgres<br/>DuckLake catalog")]
    dash["Streamlit<br/>dashboard"]

    api --> client --> extract --> bronze
    bronze --> dbt
    dbt --> silver
    dbt --> gold
    dbt <-. "table metadata,<br/>snapshots" .-> catalog
    gold --> dash

    airflow{{"Airflow<br/>daily DAG"}}
    airflow -. schedules .-> extract
    airflow -. "dbt build (Phase 4)" .-> dbt

    classDef done fill:#E1F5EE,stroke:#0F6E56,color:#085041
    classDef next fill:#F1EFE8,stroke:#888780,color:#444441
    class client,extract,bronze,silver,gold,dbt,catalog,airflow done
    class dash next
```
<sub>Green: built and running · Grey: upcoming phases</sub>

| Layer | Where | What it holds |
|-------|-------|---------------|
| **Bronze** | `s3://lakehouse/bronze/<entity>/dt=…/run=…/page=NNNN.json` | API responses byte-for-byte, one file per page, plus a `_SUCCESS.json` manifest per run. Never modified. |
| **Silver** | `s3://lakehouse/silver/<table>/*.parquet` (DuckLake schema `lake.silver`) | One table per entity, typed columns, nested arrays flattened into child tables, only the latest version of each record. |
| **Gold** | `s3://lakehouse/gold/<table>/*.parquet` (DuckLake schema `lake.gold`) | Kimball star schema, see below. |

Silver and Gold are [DuckLake](https://ducklake.select) tables: the data is Parquet in RustFS, the
catalog (which files make up which table, every snapshot) lives in Postgres. That gives ACID
writes, time travel and many concurrent readers — no database file to lock
([ADR 0004](docs/adr/0004-ducklake-for-silver-and-gold.md)).

### Gold star schema

```mermaid
erDiagram
    fct_drucksachen }o--|| dim_date : date_key
    fct_drucksachen }o--|| dim_ressort : "ressort_key (lead ministry)"
    fct_drucksachen }o--|| dim_fraktion : fraktion_key
    fct_vorgaenge }o--|| dim_date : "start / verkuendet date"
    fct_aktivitaeten }o--|| dim_date : date_key
    fct_aktivitaeten }o--|| dim_person : "person_key (SCD2, as of date)"
    fct_aktivitaeten }o--|| dim_fraktion : "fraktion_key (as printed that day)"
```

| Table | Grain | Notes |
|-------|-------|-------|
| `fct_drucksachen` | one Drucksache | lead ministry, primary originator type, Fraktion |
| `fct_vorgaenge` | one Vorgang | steps, promulgation, `dauer_tage` |
| `fct_aktivitaeten` | one Aktivität | incremental; person version and Fraktion valid on that day |
| `dim_person` | one person version | SCD Type 2 from the `snp_person` snapshot |
| `dim_fraktion`, `dim_ressort` | one Fraktion / ministry | |
| `dim_date` | one day | weekday, month, Wahlperiode |

Every dimension has an *Unbekannt* member, so facts never have NULL keys. Example questions are in
[`dbt/analyses/`](dbt/analyses/); design notes in [ADR 0005](docs/adr/0005-gold-star-schema.md).

## Stack

| Tool | Role in this project |
|------|----------------------|
| Python 3.12 · httpx · boto3 | Ingestion: API client, Bronze writer |
| [RustFS](https://github.com/rustfs/rustfs) | Local S3-compatible object store ([why not MinIO](docs/adr/0001-rustfs-as-object-store.md)) |
| Apache Airflow 3 | Daily orchestration, retries, backfills |
| dbt-core + dbt-duckdb · DuckDB | SQL transformations, tests, docs; DuckDB reads Bronze straight from S3 |
| DuckLake (catalog in Postgres) | Table format for Silver/Gold: Parquet in S3 + snapshots, time travel |
| Docker Compose | Runs RustFS, Airflow and Postgres (Airflow metadata + DuckLake catalog) locally |
| pgAdmin | Web UI for Postgres, both databases pre-registered |
| uv · ruff · pre-commit · GitHub Actions | Dependencies, linting, secret scanning, CI |

## Getting started

```bash
uv sync                          # Python env + dev tools
uv run pre-commit install        # run hooks on every commit
cp .env.example .env             # then replace every change-me value
docker compose up -d             # RustFS :9001, Airflow :8080, pgAdmin :5050 (localhost only)
```

Load data into Bronze:

```bash
uv run --env-file .env python -m ingestion backfill --days 7   # one idempotent run per day
uv run --env-file .env python -m ingestion extract              # incremental from watermarks
uv run --env-file .env python -m ingestion status
```

In Airflow, the `dip_ingestion` DAG does the same daily, one task per DIP entity.

Build and test Silver and Gold:

```bash
uv run --env-file .env dbt deps                # once: install dbt packages
uv run --env-file .env dbt build               # seeds, models, snapshot, data + unit tests
uv run --env-file .env dbt source freshness    # is Bronze up to date?
uv run --env-file .env dbt run-operation ducklake_maintenance --args '{days: 7}'  # drop old snapshots
uv run --env-file .env dbt compile --select path:analyses  # SQL for the example questions in dbt/target/compiled/
```

Explore the data in the browser (DuckDB UI, read-only, http://localhost:4213):

```bash
uv run --env-file .env python scripts/duckdb_ui.py   # Ctrl+C to stop
```

Local web UIs (all bound to localhost):

| URL | What |
|-----|------|
| http://localhost:8080 | Airflow (login from `.env`: `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD`) |
| http://localhost:9001 | RustFS console (`RUSTFS_ACCESS_KEY` / `RUSTFS_SECRET_KEY`) |
| http://localhost:5050 | pgAdmin: Airflow metadata DB and DuckLake catalog, no login needed |
| http://localhost:4213 | DuckDB UI, started by `scripts/duckdb_ui.py` |

DuckDB is embedded: there is no database server. Every process (dbt, the UI, later the
dashboard) runs its own in-memory DuckDB and attaches the shared DuckLake catalog, so they can
all work at the same time.

## Project layout

```
ingestion/          DIP API client, Bronze writer, watermarks, CLI
scripts/            Dev helpers (skill sync, DuckDB UI)
airflow/dags/       Airflow DAGs
dbt/                dbt project: sources, bronze views, silver models, tests
docs/adr/           Architecture decision records
tests/              Python unit tests
docker/             Container config (DuckLake catalog init, pgAdmin servers)
docker-compose.yml  Local stack
```

Design decisions are recorded in [`docs/adr/`](docs/adr/).

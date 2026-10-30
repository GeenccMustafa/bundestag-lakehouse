# 0006. Orchestration with Cosmos, asset-driven DAGs, dbt in CI on sample data
Date: 2026-10-30 · Status: accepted

## Context
Phase 4 has to run ingestion and dbt as one pipeline that stops when data is bad, show every dbt
model as its own Airflow task, run dbt in CI, and publish dbt's documentation. Constraints:

- Airflow and dbt pin different versions of shared libraries; installing both into one Python
  environment is fragile.
- The stack runs on a laptop. A first attempt (one dbt process per node, `dbt ls` at every DAG
  parse) pushed the scheduler to ~380 % CPU and the DAG processor to ~260 % and was stopped.
- CI has no RustFS, no Postgres and no DIP access (DIP currently challenges non-browser clients).

## Decision
- **Custom Airflow image** (`docker/airflow/Dockerfile`): Cosmos in Airflow's environment
  (pip + Airflow constraints, Airflow's documented method); dbt in its own venv
  `/opt/airflow/dbt-venv`, installed with `--require-hashes` from `dbt/requirements.txt`, which a
  pre-commit hook exports from `uv.lock`. Airflow runs exactly the dbt the repo is tested with.
- **Cosmos `DbtTaskGroup`** in `dbt_lakehouse`, tuned for low load:
  - `LoadMode.DBT_MANIFEST` from `dbt/target-airflow/manifest.json`, produced once by
    `airflow-init` (`dbt deps` + `dbt parse`), so the DAG processor never runs dbt
    (measured: ~260 % → ~3 % CPU).
  - `ExecutionMode.WATCHER`: one `dbt build` subprocess does the work; per-node tasks only watch
    its results. `dbt build` tests each model right after building it and skips everything
    downstream of a failure. `DBT_THREADS=2` in Compose.
- **Asset-driven chain**: `dip_ingestion` emits the `bronze` asset only after every entity
  succeeded; `dbt_lakehouse` is scheduled on it and emits `gold` after building, testing and
  DuckLake housekeeping.
- **dbt `ci` target**: DuckLake with a local DuckDB-file catalog and local Parquet; Bronze read
  from `dbt/sample_data/bronze` (7 real API pages, 340 KB) via `BRONZE_ROOT`. Same models, tests
  and materializations as production; a full build takes seconds and needs no services.
- **CI**: full `dbt build` on pushes to `main`; on pull requests **slim CI**
  `dbt build --select @state:modified` against a manifest parsed from the base branch. `@`
  includes the parents of all downstream nodes (seeds etc.), which an empty CI lake needs.
- **Docs**: `docs.yml` builds on the sample data, runs `dbt docs generate --static` and deploys the
  single HTML file to GitHub Pages.

## Alternatives considered
- **Cosmos `LOCAL` mode, one dbt process per node** — finest-grained retries, but far too heavy
  on a laptop (tried, stopped).
- **`LoadMode.DBT_LS`** — always current, but runs dbt on every DAG parse.
- **dbt in Airflow's environment (`DBT_RUNNER`)** — fastest invocation, but couples dependency
  upgrades of two large tools.
- **One DAG for ingestion + dbt** — simpler to read; assets keep the DAGs independently runnable
  (dbt can be triggered while DIP is unreachable) and make the data dependency explicit.
- **Slim CI with `--defer`** — the usual pattern, but needs a production warehouse to defer to;
  CI only has an empty lake.

## Consequences
- After changing the dbt project, restart `airflow-init` (or the stack) so the manifest the DAG
  renders from is regenerated.
- WATCHER retries happen at the level of the whole `dbt build`, not per model.
- CI exercises the real SQL on real (small) data; it does not catch issues that only appear at
  full data volume.
- GitHub Pages must be enabled with "GitHub Actions" as the source.

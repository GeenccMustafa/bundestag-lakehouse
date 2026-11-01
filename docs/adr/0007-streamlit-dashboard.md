# 0007. Streamlit dashboard as a read-only consumer of Gold
Date: 2026-11-01 · Status: accepted

## Context
Phase 5 puts the Gold star schema in front of people who will not write SQL. The dashboard
must:

- answer the project's questions (activity per Fraktion, papers per ministry, procedure
  duration) with filters for Wahlperiode and date range;
- never be able to change the lake, and not block dbt while it is open;
- run on a laptop that struggles with the full Airflow stack;
- be checked in CI, which has no Postgres, no RustFS and no DIP access.

## Decision
- **Streamlit + Altair**, one page (`dashboard/app.py`), run on the host with `uv run`.
  The dependencies live in their own uv group `dashboard` (included in `dev`).
- **Read-only DuckLake attach** (`dashboard/lake.py`): an in-memory DuckDB attaches the catalog
  with `READ_ONLY`, credentials from the environment only. `LAKE_TARGET` selects the real lake
  (`dev`: Postgres catalog, Parquet in RustFS) or the sample lake written by
  `dbt build --target ci`, mirroring dbt's two targets.
- **SQL kept apart from the UI** (`dashboard/queries.py`): plain functions returning DataFrames,
  every filter a bound parameter. Facts are joined to dimensions by surrogate key; unknown
  members are counted in totals but left out of per-dimension rankings.
- **Caching:** query results for ten minutes (`st.cache_data`), one connection per process
  (`st.cache_resource`) with a cursor per query, because Streamlit serves viewers from threads.
- **Freshness is shown, not scheduled:** the sidebar shows the latest DuckLake snapshot (the
  last dbt write) and the newest DIP `aktualisiert` in Gold. The dashboard does not subscribe
  to the `gold` asset; it simply reads the newest snapshot.
- **Tests:** query tests against a hand-made Gold layer in a temporary DuckLake; a `lake`-marked
  smoke test renders the whole app headless (`streamlit.testing`) on the sample lake, run by a
  CI job after the sample `dbt build`.
- **Charts:** one series each, a single accent colour, axes and a table view per chart; no
  party colours (they would need a validated palette and add nothing a sorted bar does not show).

## Alternatives considered
- **Evidence / Superset / Metabase** — richer BI, but another server (and for Superset a
  metadata DB) on an already loaded laptop, and no DuckLake support out of the box.
- **Dashboard as a Compose service** — closer to production, but rebuilding an image for each
  change slows iteration; the host process needs only Postgres and RustFS. Can be added later.
- **Querying Gold through dbt (`dbt show`)** — reuses the profile, but spawns dbt per query.
- **Export Gold to a local DuckDB file for the dashboard** — fastest reads, but a second copy
  that can go stale and a file lock that blocks the export while the app is open.

## Consequences
- After a dbt run, the dashboard shows the new data within ten minutes (cache TTL) or on
  restart.
- `fct_vorgaenge` is filtered by Wahlperiode only: most procedures' start date is unknown until
  Bronze holds their full history, and a date filter would silently drop them.
- Gold column renames break dashboard queries; the CI smoke job catches this on the sample data.
- Streamlit's hot reload only re-runs `app.py`; after changing `queries.py` or `lake.py`, restart.

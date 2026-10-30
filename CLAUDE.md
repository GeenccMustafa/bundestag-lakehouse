# Bundestag Open-Data Lakehouse

Learning project: an end-to-end Bronze → Silver → Gold lakehouse on the Bundestag DIP API. See `README.md` for the architecture and `.claude/skills/README.md` for the skills in use.

## Working style

The user doesn't write code in this project ("vibe coding"): Claude implements everything end to end.

- Before each phase, give a short explanation of the concepts and the design choices made.
- Write the code, tests and config; run them locally (Docker stack, real DIP API) and show live results.
- A phase is done only when its "done" criteria are met and verified by running the commands, not by assumption.
- Record hard-to-reverse decisions as ADRs in `docs/adr/` (see the `lakehouse-architecture` skill).
- The user communicates in Turkish; code, comments, commit messages and docs are in English.
- Docstrings: Google style (`Args:` / `Returns:` / `Raises:`), enforced by ruff's `D` rules (tests exempt). Explain *why* and contracts (idempotency, what is retried, what raises), not what the next line does.

## Commands

- Python: `uv` only — `uv add <pkg>`, `uv add --dev <pkg>`, `uv run <cmd>`, `uv sync`. Never `pip install`.
- Lint/format: `uv run ruff check .` and `uv run ruff format .`
- Tests: `uv run pytest`
- All hooks: `uv run pre-commit run --all-files`
- Stack: `docker compose up -d` (needs `.env`, see `.env.example`)
- Ingestion: `uv run --env-file .env python -m ingestion {backfill --days N|extract|status}`
- dbt: `uv run --env-file .env dbt {deps|build|source freshness}` (from repo root; `.env` sets the project/profiles dir)
- dbt without the stack: `BRONZE_ROOT=$PWD/dbt/sample_data/bronze uv run --env-file .env dbt build --target ci` (mkdir /tmp/bundestag-dbt-ci first)
- After changing dbt models: `docker compose up -d airflow-init` regenerates the manifest the Cosmos DAG renders from
- The user's laptop struggles with long runs: prefer cheap checks (DAG import, `--target ci`, CI) and ask before full Airflow runs or anything taking minutes; stop the stack when not needed
- Browse data: `uv run --env-file .env python scripts/duckdb_ui.py` (DuckDB UI on :4213, DuckLake attached read-only)
- Postgres UI: pgAdmin at http://localhost:5050 (both DBs pre-registered; `docker compose exec postgres psql -U airflow` for a shell)
- DuckLake housekeeping: `uv run --env-file .env dbt run-operation ducklake_maintenance --args '{days: 7}'`
- DIP API: keep request volume low. Bursts get redirected to a bot challenge (HTTP 303); never try to bypass it, back off instead.
- Skills: `scripts/sync-skills.sh` after editing `.claude/skills/vendor.lock`

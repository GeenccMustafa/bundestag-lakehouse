---
name: security-baseline
description: Security rules for this repo — secrets handling, Docker Compose service hardening, dependency and supply-chain hygiene, and GitHub Actions safety. Use when touching .env files, credentials, docker-compose.yml, Airflow/MinIO/Postgres config, GitHub Actions workflows, or when adding a dependency; and before any commit that might contain a secret.
---

# Security Baseline

This is a public repo. Assume everything committed is read by the world forever.

## Secrets

- Secrets only come from environment variables, loaded from a git-ignored `.env`. Commit a `.env.example` with **placeholder** values and a comment per variable.
- Never hard-code a secret, never give one a "fallback" default in code (`os.getenv("KEY", "real-value")` is a leak). Missing secret → fail fast with a clear error.
- The DIP API key is public but expiring; it is still treated as a secret (env var `DIP_API_KEY`) so rotation needs no code change and keys from other services follow the same path.
- Never log secrets or full request URLs that may contain them; send API keys in headers, not query params.
- Run a secret scanner in pre-commit and CI (e.g. `gitleaks`). If a secret is ever committed: rotate it first, then clean history — rotating is what actually helps.

## Docker Compose services

- No default credentials (`minioadmin`, `airflow/airflow`, `postgres/postgres`) — read them from `.env`.
- Generate Airflow's `FERNET_KEY` and webserver secret key; never commit them.
- Bind ports to localhost: `"127.0.0.1:9000:9000"`, not `"9000:9000"` — the latter is reachable from your whole network.
- Pin image tags to a version (`minio/minio:RELEASE.2025-…`, `apache/airflow:3.x.y`), never `latest`.
- Postgres for Airflow is internal only: no published port unless needed for debugging.

## Dependencies / supply chain

- Add dependencies only with `uv add`; commit `uv.lock`. CI installs with `uv sync --locked` so it fails if the lock is stale.
- Before adding a new package, check it's maintained and widely used; prefer the standard library or an existing dependency.
- Enable Dependabot (or Renovate) for `uv`, GitHub Actions and Docker images.
- Run `uvx pip-audit` (or equivalent) in CI.

## GitHub Actions

- `permissions:` set explicitly at workflow level, default `contents: read`; widen per job only when needed (e.g. `pages: write` for dbt docs).
- Pin third-party actions to a full commit SHA (with the version in a comment).
- Never use `pull_request_target` with a checkout of PR code. Never interpolate `${{ github.event.* }}` user-controlled fields directly into `run:` — pass them through `env:`.
- CI uses sample/fixture data only; no real API key needed for tests.

## Code-level checks

- Ruff's `S` (bandit) rules stay enabled.
- SQL: in Python, never build SQL with f-strings from external input — use DuckDB parameters. In dbt, Jinja-generated SQL is fine because inputs are our own config.
- For reviewing a diff with a security lens, use the `differential-review` skill.

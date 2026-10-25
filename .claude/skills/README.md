# Claude skills for this project

Claude Code loads every `*/SKILL.md` in this folder and pulls a skill in when its `description` matches the task.

## Project skills (owned here, edit freely)

| Skill | Area | Used in |
|-------|------|---------|
| `lakehouse-architecture` | Layer contracts, naming, ADRs | All phases |
| `dip-api-ingestion` | DIP API facts, incremental + idempotent loads | Phase 1 |
| `dimensional-modeling` | Kimball, grain, SCD2, incremental marts | Phase 3 |
| `security-baseline` | Secrets, Compose hardening, supply chain, Actions | Phases 0, 4 |

## Vendored skills (third-party, managed by `vendor.lock`)

| Skill | Source | License | Area |
|-------|--------|---------|------|
| `modern-python` | trailofbits/skills | CC-BY-SA-4.0 | uv, ruff, pyproject, pre-commit |
| `differential-review` | trailofbits/skills | CC-BY-SA-4.0 | Security review of diffs |
| `test-driven-development` | obra/superpowers | MIT | Code quality |
| `systematic-debugging` | obra/superpowers | MIT | Root-cause debugging |
| `verification-before-completion` | obra/superpowers | MIT | Evidence before "done" |
| `using-dbt-for-analytics-engineering` | dbt-labs/dbt-agent-skills | Apache-2.0 | dbt models, tests, docs |
| `adding-dbt-unit-test` | dbt-labs/dbt-agent-skills | Apache-2.0 | dbt unit tests |
| `running-dbt-commands` | dbt-labs/dbt-agent-skills | Apache-2.0 | dbt CLI usage |
| `cosmos-dbt-core` | astronomer/agents | Apache-2.0 | Airflow + Cosmos (Phase 4) |

Each vendored folder has a `.upstream` file (repo, path, commit) and `LICENSE.upstream`. Don't edit vendored files; if one needs changes, copy it into a new project skill instead.

## Adding or removing skills

- **Vendored**: add or delete a line in `vendor.lock` (use `HEAD` as the sha for the latest), then run `scripts/sync-skills.sh`. Skills dropped from the lock are deleted; project skills are never touched.
- **Update vendored skills**: set the sha to `HEAD` and re-run the script.
- **Project skill**: create `<name>/SKILL.md` with `name` + `description` front matter. The description decides when it triggers, so say *what* it covers and *when* to use it.
- Review this list at the end of each phase: drop skills that never triggered or weren't helpful.

Candidates for later: `astronomer/agents` → `authoring-dags`, `debugging-dags`; `trailofbits/skills` → `sharp-edges`, `property-based-testing`, `supply-chain-risk-auditor`; `dbt-labs/dbt-agent-skills` → `maintaining-dbt-documentation`.

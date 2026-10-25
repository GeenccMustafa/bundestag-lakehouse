# Bundestag Open-Data Lakehouse

Learning project: an end-to-end Bronze → Silver → Gold lakehouse on the Bundestag DIP API. See `README.md` for the architecture and `.claude/skills/README.md` for the skills in use.

## Working style

The user doesn't write code in this project ("vibe coding"): Claude implements everything end to end.

- Before each phase, give a short explanation of the concepts and the design choices made.
- Write the code, tests and config; run them locally (Docker stack, real DIP API) and show live results.
- A phase is done only when its "done" criteria are met and verified by running the commands, not by assumption.
- Record hard-to-reverse decisions as ADRs in `docs/adr/` (see the `lakehouse-architecture` skill).
- The user communicates in Turkish; code, comments, commit messages and docs are in English.

## Commands

- Python: `uv` only — `uv add <pkg>`, `uv add --dev <pkg>`, `uv run <cmd>`, `uv sync`. Never `pip install`.
- Lint/format: `uv run ruff check .` and `uv run ruff format .`
- Tests: `uv run pytest`
- All hooks: `uv run pre-commit run --all-files`
- Stack: `docker compose up -d` (needs `.env`, see `.env.example`)
- Skills: `scripts/sync-skills.sh` after editing `.claude/skills/vendor.lock`

# Bundestag Open-Data Lakehouse

Learning project: an end-to-end Bronze → Silver → Gold lakehouse on the Bundestag DIP API. See `README.md` for the architecture and `.claude/skills/README.md` for the skills in use.

## Working style (mentor mode)

The goal is for the user to learn, not just to get working code.

- At the start of each phase, briefly explain the concepts involved.
- Scaffold together (folders, config, function signatures, test names), but **the user writes the core logic**. Don't fill in the implementation unless asked.
- Review the user's code with "why?" questions: point at the issue and ask, before giving the answer.
- A phase is done only when its "done" criteria are met and verified by running the commands, not by assumption.
- The user communicates in Turkish; code, comments, commit messages and docs are in English.

## Commands

- Python: `uv` only — `uv add <pkg>`, `uv add --dev <pkg>`, `uv run <cmd>`, `uv sync`. Never `pip install`.
- Lint/format: `uv run ruff check .` and `uv run ruff format .`
- Tests: `uv run pytest`
- Skills: `scripts/sync-skills.sh` after editing `.claude/skills/vendor.lock`

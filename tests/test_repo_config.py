"""Smoke tests that guard the repo's configuration contracts."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_python_version_pinned_to_312() -> None:
    assert (ROOT / ".python-version").read_text().strip() == "3.12"
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["requires-python"] == ">=3.12"


def test_env_example_covers_every_compose_variable() -> None:
    lines = (ROOT / "docker-compose.yml").read_text().splitlines()
    compose = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
    # `$${VAR}` is an escaped, container-side variable, not one Compose reads from .env.
    used = set(re.findall(r"(?<!\$)\$\{([A-Z0-9_]+)", compose))
    documented = {
        line.split("=", 1)[0]
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line and not line.startswith("#")
    }
    assert used <= documented, f"missing in .env.example: {sorted(used - documented)}"


def test_compose_ports_bound_to_localhost() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    published = re.findall(r'^\s*-\s*"([^"]*:\d+:\d+)"', compose, flags=re.M)
    assert published, "expected at least one published port"
    assert all(p.startswith("127.0.0.1:") for p in published), published

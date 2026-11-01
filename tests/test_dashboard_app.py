"""Render the whole dashboard headless against the sample-data lake.

Needs the lake `dbt build --target ci` writes (marker `lake`, run in CI after that build):

    uv run pytest -m lake
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"

pytestmark = pytest.mark.lake


def test_app_renders_every_panel_without_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKE_TARGET", "ci")
    at = AppTest.from_file(str(APP), default_timeout=60).run()

    assert not at.exception
    assert not at.error
    assert [m.label for m in at.metric] == [
        "Drucksachen",
        "Vorgänge",
        "Aktivitäten",
        "Aktive Personen",
    ]
    assert all(m.value != "0" for m in at.metric), [m.value for m in at.metric]
    assert "Aktivitäten je Fraktion" in [h.value for h in at.subheader]


def test_choosing_a_wahlperiode_rerenders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKE_TARGET", "ci")
    at = AppTest.from_file(str(APP), default_timeout=60).run()

    wahlperiode = at.sidebar.selectbox[0]
    # The sample pages are from the 21st Bundestag. set_value takes the raw option; select()
    # would apply format_func to the already formatted label.
    wahlperiode.set_value(21).run()

    assert at.sidebar.selectbox[0].value == 21

    assert not at.exception
    assert not at.error

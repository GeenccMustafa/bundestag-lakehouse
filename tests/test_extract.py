import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from ingestion.client import DipApiError
from ingestion.extract import (
    NoWatermarkError,
    Window,
    incremental_window,
    run_extract,
    window_run_id,
)
from ingestion.storage import InMemoryObjectStore
from ingestion.watermark import load_watermark
from tests.conftest import FakeDip, page

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
DAY = Window(datetime(2026, 10, 23, tzinfo=UTC), datetime(2026, 10, 24, tzinfo=UTC))
RUN_DATE = date(2026, 10, 23)


def _run(make_client, store, responses, window=DAY, run_id=None):
    client, _ = make_client(FakeDip(responses), page_delay=0)
    return run_extract(
        client,
        store,
        "vorgang",
        window,
        run_id=run_id or window_run_id(window),
        run_date=RUN_DATE,
        now=NOW,
    )


def test_writes_raw_pages_then_manifest(make_client, vorgang_page) -> None:
    store = InMemoryObjectStore()
    docs = vorgang_page["documents"]

    result = _run(make_client, store, [page(docs[:2], "c1"), page(docs[2:], "c2"), page([], "c2")])

    prefix = "bronze/vorgang/dt=2026-10-23/run=20261023T000000Z_20261024T000000Z/"
    assert result.prefix == prefix
    assert store.list(prefix) == [
        f"{prefix}_SUCCESS.json",
        f"{prefix}page=0001.json",
        f"{prefix}page=0002.json",
    ]
    assert json.loads(store.get(f"{prefix}page=0001.json"))["documents"] == docs[:2]
    manifest = json.loads(store.get(f"{prefix}_SUCCESS.json"))
    assert manifest["pages"] == 2
    assert manifest["documents"] == 3
    assert manifest["window"] == {
        "start": "2026-10-23T00:00:00+00:00",
        "end": "2026-10-24T00:00:00+00:00",
    }


def test_sends_window_as_utc_aktualisiert_filter(make_client) -> None:
    store = InMemoryObjectStore()
    fake = FakeDip([page([], "c"), page([], "c")])
    client, _ = make_client(fake)

    run_extract(client, store, "vorgang", DAY, run_id="r", run_date=RUN_DATE, now=NOW)

    params = fake.requests[0].url.params
    assert params["f.aktualisiert.start"] == "2026-10-23T00:00:00+00:00"
    assert params["f.aktualisiert.end"] == "2026-10-24T00:00:00+00:00"


def test_rerun_replaces_previous_output(make_client, vorgang_page) -> None:
    """Idempotency: a re-run with fewer pages must not leave stale pages behind."""
    store = InMemoryObjectStore()
    docs = vorgang_page["documents"]
    _run(make_client, store, [page(docs[:1], "c1"), page(docs[1:], "c2"), page([], "c2")])

    result = _run(make_client, store, [page(docs, "c1"), page([], "c1")])

    pages = [k for k in store.list("bronze/") if "/page=" in k]
    assert pages == [f"{result.prefix}page=0001.json"]


def test_same_window_gives_same_keys(make_client, vorgang_page) -> None:
    docs = vorgang_page["documents"]
    first, second = InMemoryObjectStore(), InMemoryObjectStore()
    _run(make_client, first, [page(docs, "c1"), page([], "c1")])
    _run(make_client, second, [page(docs, "c1"), page([], "c1")])

    assert first.objects == second.objects


def test_watermark_is_max_aktualisiert(make_client, vorgang_page) -> None:
    store = InMemoryObjectStore()

    _run(make_client, store, [page(vorgang_page["documents"], "c1"), page([], "c1")])

    wm = load_watermark(store, "vorgang")
    assert wm is not None
    assert wm.max_aktualisiert == datetime.fromisoformat("2026-10-23T14:13:27+02:00")
    assert wm.last_run_id == window_run_id(DAY)


def test_watermark_never_moves_backwards(make_client) -> None:
    store = InMemoryObjectStore()
    newer = [{"id": "1", "aktualisiert": "2026-10-24T10:00:00+02:00"}]
    older = [{"id": "2", "aktualisiert": "2026-10-01T10:00:00+02:00"}]
    _run(make_client, store, [page(newer, "c"), page([], "c")], run_id="new")

    _run(make_client, store, [page(older, "c"), page([], "c")], run_id="old-backfill")

    wm = load_watermark(store, "vorgang")
    assert wm.max_aktualisiert == datetime.fromisoformat(newer[0]["aktualisiert"])
    assert wm.last_run_id == "new"


def test_failed_run_leaves_watermark_and_no_manifest(make_client, vorgang_page) -> None:
    store = InMemoryObjectStore()
    responses = [page(vorgang_page["documents"], "c1"), httpx.Response(401)]

    with pytest.raises(DipApiError):
        _run(make_client, store, responses)

    assert load_watermark(store, "vorgang") is None
    assert not [k for k in store.list("bronze/") if k.endswith("_SUCCESS.json")]


def test_incremental_window_starts_before_watermark(make_client) -> None:
    store = InMemoryObjectStore()
    docs = [{"id": "1", "aktualisiert": "2026-10-24T10:00:00+00:00"}]
    _run(make_client, store, [page(docs, "c"), page([], "c")])

    window = incremental_window(store, "vorgang", NOW, overlap=timedelta(hours=1))

    assert window.start == datetime(2026, 10, 24, 9, 0, tzinfo=UTC)
    assert window.end == NOW


def test_incremental_without_watermark_fails_loudly() -> None:
    with pytest.raises(NoWatermarkError, match="backfill"):
        incremental_window(InMemoryObjectStore(), "vorgang", NOW)


def test_naive_timestamps_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Window(start=datetime(2026, 1, 1)).params()

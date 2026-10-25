"""Extract one DIP entity for one time window into Bronze, idempotently.

Bronze layout (hive-style, so DuckDB can read `dt` and `run` as columns):

    bronze/<entity>/dt=<YYYY-MM-DD>/run=<run_id>/page=0001.json   raw API response, byte-exact
    bronze/<entity>/dt=<YYYY-MM-DD>/run=<run_id>/_SUCCESS.json     manifest, written last

A run first deletes its own `run=` prefix, so re-running the same run id replaces its
output instead of adding to it. The watermark only moves after the manifest is written.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from ingestion.client import DipClient
from ingestion.storage import ObjectStore
from ingestion.watermark import Watermark, advance_watermark, load_watermark

log = logging.getLogger(__name__)

DEFAULT_OVERLAP = timedelta(hours=1)


class NoWatermarkError(RuntimeError):
    pass


@dataclass(frozen=True)
class Window:
    """Filter on `aktualisiert`. None on both ends means a full load."""

    start: datetime | None = None
    end: datetime | None = None

    def params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.start is not None:
            params["f.aktualisiert.start"] = _iso(self.start)
        if self.end is not None:
            params["f.aktualisiert.end"] = _iso(self.end)
        return params


@dataclass(frozen=True)
class RunResult:
    entity: str
    run_id: str
    prefix: str
    pages: int
    documents: int
    max_aktualisiert: datetime | None
    watermark: Watermark | None


def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {ts!r}")
    # Always send an explicit offset: without one DIP interprets the time as Berlin local time.
    return ts.astimezone(UTC).isoformat(timespec="seconds")


def _compact(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def window_run_id(window: Window) -> str:
    """Deterministic id for a window, so a re-run of the same window overwrites itself."""
    start = _compact(window.start) if window.start else "begin"
    end = _compact(window.end) if window.end else "open"
    return f"{start}_{end}"


def bronze_prefix(entity: str, run_date: date, run_id: str) -> str:
    return f"bronze/{entity}/dt={run_date.isoformat()}/run={run_id}/"


def incremental_window(
    store: ObjectStore, entity: str, now: datetime, overlap: timedelta = DEFAULT_OVERLAP
) -> Window:
    """From the last watermark (minus an overlap for late commits / clock skew) up to now."""
    watermark = load_watermark(store, entity)
    if watermark is None:
        raise NoWatermarkError(
            f"No watermark for '{entity}' yet. Run a backfill or full load first."
        )
    return Window(start=watermark.max_aktualisiert - overlap, end=now)


def run_extract(
    client: DipClient,
    store: ObjectStore,
    entity: str,
    window: Window,
    *,
    run_id: str,
    run_date: date,
    now: datetime | None = None,
) -> RunResult:
    now = now or datetime.now(UTC)
    prefix = bronze_prefix(entity, run_date, run_id)
    removed = store.delete_prefix(prefix)
    if removed:
        log.info("%s: replacing %d objects from a previous attempt of %s", entity, removed, run_id)

    pages = documents = 0
    max_aktualisiert: datetime | None = None
    page_log: list[dict[str, object]] = []

    for page in client.iter_pages(entity, window.params()):
        key = f"{prefix}page={page.number:04d}.json"
        store.put(key, page.body)
        pages += 1
        documents += len(page.documents)
        for doc in page.documents:
            if ts := doc.get("aktualisiert"):
                parsed = datetime.fromisoformat(ts)
                if max_aktualisiert is None or parsed > max_aktualisiert:
                    max_aktualisiert = parsed
        page_log.append(
            {
                "key": key,
                "params": page.params,
                "status": page.status_code,
                "documents": len(page.documents),
            }
        )
        log.info("%s: page %d, %d documents", entity, page.number, len(page.documents))

    manifest = {
        "entity": entity,
        "run_id": run_id,
        "run_date": run_date.isoformat(),
        "window": {k: (_iso(v) if v else None) for k, v in vars(window).items()},
        "fetched_at": _iso(now),
        "pages": pages,
        "documents": documents,
        "max_aktualisiert": max_aktualisiert.isoformat() if max_aktualisiert else None,
        "page_log": page_log,
    }
    store.put(f"{prefix}_SUCCESS.json", json.dumps(manifest, indent=2).encode())

    watermark = None
    if max_aktualisiert is not None:
        watermark = advance_watermark(
            store,
            Watermark(
                entity=entity,
                max_aktualisiert=max_aktualisiert,
                last_run_id=run_id,
                updated_at=now,
            ),
        )
    else:
        watermark = load_watermark(store, entity)

    log.info("%s: %d documents in %d pages -> %s", entity, documents, pages, prefix)
    return RunResult(entity, run_id, prefix, pages, documents, max_aktualisiert, watermark)

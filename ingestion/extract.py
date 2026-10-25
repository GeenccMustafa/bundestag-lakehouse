"""Extract one DIP entity for one time window into Bronze, idempotently.

Bronze layout (hive-style, so DuckDB can read `dt` and `run` as columns):

    bronze/<entity>/dt=<YYYY-MM-DD>/run=<run_id>/page=0001.json   raw API response, byte-exact
    bronze/<entity>/dt=<YYYY-MM-DD>/run=<run_id>/_SUCCESS.json     manifest, written last

A run first deletes its own ``run=`` prefix, so re-running the same run id replaces its
output instead of adding to it. The watermark only moves after the manifest is written, so a
run that fails half-way leaves no manifest and no watermark change. See docs/adr/0002.
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
"""How far before the watermark incremental runs start, to catch late commits and clock skew."""


class NoWatermarkError(RuntimeError):
    """An incremental run was requested for an entity that has never been loaded."""


@dataclass(frozen=True)
class Window:
    """Time window on the DIP ``aktualisiert`` (last modified) field.

    Both bounds must be timezone-aware. A missing bound leaves that side open; a window with
    no bounds at all is a full load.

    Attributes:
        start: Lower bound for ``aktualisiert`` (``f.aktualisiert.start``), or None.
        end: Upper bound for ``aktualisiert`` (``f.aktualisiert.end``), or None.
    """

    start: datetime | None = None
    end: datetime | None = None

    def params(self) -> dict[str, str]:
        """Return the window as DIP query parameters (``f.aktualisiert.start`` / ``.end``).

        Raises:
            ValueError: If a bound is a naive datetime.
        """
        params: dict[str, str] = {}
        if self.start is not None:
            params["f.aktualisiert.start"] = _iso(self.start)
        if self.end is not None:
            params["f.aktualisiert.end"] = _iso(self.end)
        return params


@dataclass(frozen=True)
class RunResult:
    """Outcome of one `run_extract` call.

    Attributes:
        entity: DIP entity that was extracted.
        run_id: Id of the run, part of the Bronze path.
        prefix: Bronze prefix the run wrote to.
        pages: Number of pages written.
        documents: Number of records across all pages (duplicates included).
        max_aktualisiert: Newest ``aktualisiert`` seen, or None if the window was empty.
        watermark: Watermark in effect after the run, or None if the entity has none yet.
    """

    entity: str
    run_id: str
    prefix: str
    pages: int
    documents: int
    max_aktualisiert: datetime | None
    watermark: Watermark | None


def _iso(ts: datetime) -> str:
    """Format a timezone-aware datetime as ISO-8601 in UTC, to the second."""
    if ts.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {ts!r}")
    # Always send an explicit offset: without one DIP interprets the time as Berlin local time.
    return ts.astimezone(UTC).isoformat(timespec="seconds")


def _compact(ts: datetime) -> str:
    """Format a datetime as ``YYYYMMDDTHHMMSSZ`` (UTC), safe for object keys."""
    return ts.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def window_run_id(window: Window) -> str:
    """Return a deterministic run id for `window`, e.g. ``20261022T000000Z_20261023T000000Z``.

    The same window always yields the same id, and therefore the same Bronze prefix, so
    re-running it overwrites the earlier output instead of duplicating it.
    """
    start = _compact(window.start) if window.start else "begin"
    end = _compact(window.end) if window.end else "open"
    return f"{start}_{end}"


def bronze_prefix(entity: str, run_date: date, run_id: str) -> str:
    """Return the Bronze prefix of a run: ``bronze/<entity>/dt=<date>/run=<run_id>/``."""
    return f"bronze/{entity}/dt={run_date.isoformat()}/run={run_id}/"


def incremental_window(
    store: ObjectStore, entity: str, now: datetime, overlap: timedelta = DEFAULT_OVERLAP
) -> Window:
    """Return the window for an incremental run: from the watermark minus `overlap` to `now`.

    Records in the overlap are fetched twice; Silver keeps only the latest version.

    Args:
        store: Where watermarks are kept.
        entity: DIP entity.
        now: End of the window (timezone-aware).
        overlap: How far before the watermark to start.

    Returns:
        The window to extract.

    Raises:
        NoWatermarkError: If the entity has never been loaded; run a backfill first.
    """
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
    """Extract one entity for one window into Bronze, idempotently.

    Steps: delete anything under the run's prefix (from an earlier attempt), write every API
    page byte-exact as ``page=NNNN.json``, write the ``_SUCCESS.json`` manifest, then advance
    the watermark. If the API fails part-way, the exception propagates before the manifest and
    the watermark are written; the pages already written stay until the next attempt with the
    same run id replaces them, and readers can tell them apart by the missing manifest.

    Args:
        client: Open DIP client.
        store: Bronze object store.
        entity: DIP entity, e.g. ``"vorgang"``.
        window: ``aktualisiert`` window to extract.
        run_id: Run id; use `window_run_id` so retries overwrite the same prefix.
        run_date: Partition date (``dt=``) of the run.
        now: Timestamp recorded as ``fetched_at`` / ``updated_at``; defaults to the current
            UTC time. Tests pass a fixed value.

    Returns:
        Counts, paths and the resulting watermark.

    Raises:
        DipApiError: If the API request fails for good.
        ValueError: If a window bound is a naive datetime.
    """
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

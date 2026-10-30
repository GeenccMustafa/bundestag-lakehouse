---
name: dip-api-ingestion
description: Facts about the Bundestag DIP API (endpoints, auth, cursor paging, update filters) and the incremental, idempotent ingestion patterns this project uses to land it in Bronze. Use when writing or reviewing anything in ingestion/, the API client, watermarks, backfills, or the ingestion Airflow tasks; or when debugging missing, duplicated or stale DIP data.
---

# DIP API Ingestion

## API facts (from the official OpenAPI spec v1.5)

- Base URL: `https://search.dip.bundestag.de/api/v1`
- Spec: `https://search.dip.bundestag.de/api/v1/openapi.yaml` — check it before assuming a field or filter exists.
- **Auth**: header `Authorization: ApiKey <key>` (preferred) or query param `apikey=<key>`. Use the header so the key never lands in logged URLs. The public key published on dip.bundestag.de expires periodically; it comes from the `DIP_API_KEY` env var, never from code.
- **List endpoints**: `vorgang`, `vorgangsposition`, `drucksache`, `drucksache-text`, `plenarprotokoll`, `plenarprotokoll-text`, `aktivitaet`, `person`. Each also has `/<entity>/{id}`.
- **Response shape**: `{ "numFound": int, "cursor": str, "documents": [...] }`.
- **Cursor paging**: repeat the *exact same* query params and add `cursor=<cursor from last response>`. **Stop when the returned cursor equals the one you sent** — that signals the end. Do not stop on an empty page alone, and do not compute pages from `numFound`.
- **Incremental filter**: `f.aktualisiert.start` / `f.aktualisiert.end` (ISO date-time; without an offset it is interpreted as Berlin local time — always send an explicit offset, e.g. `2024-01-01T00:00:00+00:00`).
- Other useful filters: `f.datum.start` / `f.datum.end` (document date — good for backfill ranges), `f.wahlperiode`, `f.id`.
- Errors: `400` (bad param / "Invalid cursor"), `401` (missing/expired key), `404`. Treat `429` and `5xx` as retryable; `400`/`401`/`404` are not.
- Rate limits aren't stated in the spec. Be a polite client: sequential requests per entity, a small delay between pages, exponential backoff with jitter on retryable errors, and a descriptive `User-Agent`.
- Records get **updated after first publication** (`aktualisiert` changes). The same id will therefore appear in several Bronze files over time; dedup happens in Silver, not here.

## Ingestion patterns

**Incremental load with a watermark**
1. Read the watermark for the entity (`state/watermarks/<entity>.json`, e.g. `{"aktualisiert_start": "...", "last_run_id": "..."}`).
2. Query with `f.aktualisiert.start = watermark - overlap` (a small overlap, e.g. 1 hour, guards against clock skew and late commits; duplicates are fine because Silver dedups).
3. Write every page to Bronze.
4. **Only after all pages are written successfully**, advance the watermark to the max `aktualisiert` seen (not "now" — the API clock and yours differ).

**Idempotency**
- Deterministic object keys derived from (entity, logical date, run id, page number), so a retried run overwrites instead of duplicating.
- A failed run never moves the watermark, so re-running picks up from the same place.
- Full load and backfill use the same code path with different filter params (`f.datum.*` ranges, or no `aktualisiert` filter).

**Bronze writes** (ADR 0002)
- Each response body is stored byte-exact as `page=NNNN.json`; request params, status and counts go into the run's `_SUCCESS.json` manifest, written last.
- Airflow runs use their data interval (+1h overlap) as the window; the DAG must use `CronDataIntervalTimetable`, because Airflow 3's default cron timetable gives zero-length intervals.

**Observed API behaviour** (2026-10)
- Results come sorted by `aktualisiert` descending; ids are strings.
- `numFound` is informational only; the terminal request returns an empty page with the same cursor.
- No rate-limit headers are returned.
- Since 2026-10-25 every DIP and bundestag.de URL (API, openapi.yaml, website) answers this machine's non-browser requests with `303 -> /.enodia/challenge`. Do not work around it (no browser automation, no other IPs); pause the ingestion DAG and ask the user (own API key / contact parlamentsdokumentation@bundestag.de).

## Testing

- Unit-test the paging loop and retry logic against a **fake transport** (e.g. `httpx.MockTransport`) — no live calls in unit tests or CI.
- Key cases: cursor stops when unchanged; retry on 429/503 then succeed; no retry on 401; watermark not advanced on mid-run failure; re-run produces identical object keys.
- Keep a few small recorded JSON responses under `tests/fixtures/dip/` for realistic shapes.

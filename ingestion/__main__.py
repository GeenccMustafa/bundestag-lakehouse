"""Command line entry point.

uv run python -m ingestion backfill --days 30          # daily windows, idempotent
uv run python -m ingestion extract --entity vorgang    # incremental from the watermark
uv run python -m ingestion extract --mode full --entity person
uv run python -m ingestion status
"""

import argparse
import logging
import sys
from datetime import UTC, date, datetime, time, timedelta

from ingestion import ENTITIES
from ingestion.client import DipClient
from ingestion.config import Settings
from ingestion.extract import Window, incremental_window, run_extract, window_run_id
from ingestion.storage import S3ObjectStore
from ingestion.watermark import load_watermark


def _entities(value: str) -> list[str]:
    if value == "all":
        return list(ENTITIES)
    names = value.split(",")
    unknown = set(names) - set(ENTITIES)
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown entity: {', '.join(sorted(unknown))}")
    return names


def _utc_day(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=UTC)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    ex = sub.add_parser("extract", help="one run per entity")
    ex.add_argument("--entity", type=_entities, default=list(ENTITIES), help="name, a,b or all")
    ex.add_argument("--mode", choices=["incremental", "full"], default="incremental")

    bf = sub.add_parser("backfill", help="one run per entity per UTC day")
    bf.add_argument("--entity", type=_entities, default=list(ENTITIES))
    bf.add_argument("--days", type=int, help="last N days up to today (UTC)")
    bf.add_argument("--start", type=date.fromisoformat, help="first day, YYYY-MM-DD")
    bf.add_argument("--end", type=date.fromisoformat, help="last day, YYYY-MM-DD (inclusive)")

    sub.add_parser("status", help="watermarks and Bronze object counts")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = Settings.from_env()
    store = S3ObjectStore(
        settings.bucket, settings.s3_endpoint_url, settings.s3_access_key, settings.s3_secret_key
    )
    store.ensure_bucket()

    if args.command == "status":
        for entity in ENTITIES:
            wm = load_watermark(store, entity)
            objects = store.list(f"bronze/{entity}/")
            pages = sum(1 for k in objects if "/page=" in k)
            runs = sum(1 for k in objects if k.endswith("_SUCCESS.json"))
            mark = wm.max_aktualisiert.isoformat() if wm else "-"
            print(f"{entity:18} runs={runs:<4} pages={pages:<5} watermark={mark}")
        return 0

    now = datetime.now(UTC)
    with DipClient(settings.dip_api_key, settings.dip_base_url) as client:
        if args.command == "extract":
            for entity in args.entity:
                if args.mode == "full":
                    window = Window()
                    run_id = f"full_{now:%Y%m%dT%H%M%SZ}"
                else:
                    window = incremental_window(store, entity, now)
                    run_id = window_run_id(window)
                run_extract(
                    client, store, entity, window, run_id=run_id, run_date=now.date(), now=now
                )
            return 0

        # backfill
        if args.days:
            start, end = now.date() - timedelta(days=args.days - 1), now.date()
        elif args.start:
            start, end = args.start, args.end or now.date()
        else:
            parser.error("backfill needs --days or --start")
        day = start
        while day <= end:
            window = Window(start=_utc_day(day), end=_utc_day(day + timedelta(days=1)))
            for entity in args.entity:
                run_extract(
                    client,
                    store,
                    entity,
                    window,
                    run_id=window_run_id(window),
                    run_date=day,
                    now=now,
                )
            day += timedelta(days=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())

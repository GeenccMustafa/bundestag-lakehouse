"""Daily DIP → Bronze ingestion, one task per entity.

Each run extracts records whose `aktualisiert` falls in the run's data interval (plus a
one-hour overlap). The DAG uses CronDataIntervalTimetable: Airflow 3's default for a cron
string (CronTriggerTimetable) gives runs a zero-length interval, which would only fetch the
overlap hour. The interval decides the Bronze run id, so retrying or clearing a run
overwrites its own output — runs are idempotent. History is filled with Airflow backfills:

    airflow backfill create --dag-id dip_ingestion --from-date 2026-10-01 --to-date 2026-10-24

When every entity is loaded, `bronze_ready` emits the BRONZE asset event, which starts the
dbt_lakehouse DAG. A failed extract therefore stops the pipeline before dbt runs on half-loaded
data.
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, get_current_context, task
from airflow.timetables.interval import CronDataIntervalTimetable
from lakehouse_assets import BRONZE

from ingestion import ENTITIES

OVERLAP = timedelta(hours=1)
"""Added before each interval's start, like the CLI's incremental overlap."""


@dag(
    schedule=CronDataIntervalTimetable("@daily", timezone="UTC"),
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["ingestion", "bronze", "dip"],
    doc_md=__doc__,
)
def dip_ingestion() -> None:
    """Define one `extract_<entity>` task per DIP entity; the tasks are independent."""

    @task
    def extract(entity: str) -> dict[str, object]:
        """Extract one DIP entity for this run's data interval into Bronze.

        The window is the data interval widened by `OVERLAP` at the start. Manual runs
        without a logical date fall back to the last complete UTC day.

        Returns:
            Bronze prefix, page count and document count; pushed to XCom.
        """
        from ingestion.client import DipClient
        from ingestion.config import Settings
        from ingestion.extract import Window, run_extract, window_run_id
        from ingestion.storage import S3ObjectStore

        context = get_current_context()
        start, end = context.get("data_interval_start"), context.get("data_interval_end")
        if start is None or end is None:
            # Manual run without a logical date: take the last complete UTC day, so the
            # run id is still deterministic.
            end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=1)
        window = Window(start=start - OVERLAP, end=end)

        settings = Settings.from_env()
        store = S3ObjectStore(
            settings.bucket,
            settings.s3_endpoint_url,
            settings.s3_access_key,
            settings.s3_secret_key,
        )
        store.ensure_bucket()
        with DipClient(settings.dip_api_key, settings.dip_base_url) as client:
            result = run_extract(
                client,
                store,
                entity,
                window,
                run_id=window_run_id(window),
                run_date=start.date(),
            )
        return {"prefix": result.prefix, "pages": result.pages, "documents": result.documents}

    @task(outlets=[BRONZE])
    def bronze_ready(results: list[dict[str, object]]) -> int:
        """Emit the BRONZE asset event once all entities succeeded; returns the document count."""
        return sum(int(r["documents"]) for r in results)

    bronze_ready([extract.override(task_id=f"extract_{entity}")(entity) for entity in ENTITIES])


dip_ingestion()

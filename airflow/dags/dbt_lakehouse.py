"""Build and test Silver and Gold with dbt, one Airflow task per dbt node (Astronomer Cosmos).

Runs whenever dip_ingestion has loaded Bronze (BRONZE asset event) and can be triggered by hand.
Cosmos renders every seed, model and snapshot as its own task, in dbt's dependency order.

Built to be light on a laptop:
- Parsing reads `target-airflow/manifest.json`, produced once by airflow-init (`dbt parse`), so
  the DAG processor never runs dbt.
- Execution uses Cosmos' WATCHER mode: a single `dbt build` process (the producer task) does all
  the work, and each node's task only watches its result. `dbt build` runs every model's tests
  right after it and skips everything downstream of a failure, so bad data never reaches Gold.

After a successful build the GOLD asset event is emitted and old DuckLake snapshots are pruned.

dbt lives in its own virtualenv in the image (/opt/airflow/dbt-venv) and is called as a
subprocess, so its dependencies never clash with Airflow's.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag
from cosmos import (
    DbtTaskGroup,
    ExecutionConfig,
    ExecutionMode,
    InvocationMode,
    LoadMode,
    ProfileConfig,
    ProjectConfig,
    RenderConfig,
)
from lakehouse_assets import BRONZE, GOLD

DBT_PROJECT_DIR = Path("/opt/airflow/dbt")
DBT_EXECUTABLE = "/opt/airflow/dbt-venv/bin/dbt"
# Written by airflow-init; separate from target/ so host-side dbt runs never overwrite it.
DBT_MANIFEST = DBT_PROJECT_DIR / "target-airflow" / "manifest.json"

_project = ProjectConfig(
    dbt_project_path=DBT_PROJECT_DIR,
    # airflow-init runs `dbt deps` once into the mounted project; tasks reuse dbt_packages/
    # instead of downloading packages on every run.
    install_dbt_deps=False,
    manifest_path=DBT_MANIFEST,
    # The mounted target/ may hold a partial-parse cache written by dbt on the host, where the
    # project path differs (relative `dbt/`). Reusing it makes paths such as seed files resolve
    # wrongly inside the container, so always parse fresh.
    partial_parse=False,
)
_profile = ProfileConfig(
    profile_name="bundestag",
    target_name="dev",
    # The repo's profiles.yml reads all credentials from env vars set in docker-compose.yml.
    profiles_yml_filepath=DBT_PROJECT_DIR / "profiles.yml",
)
_execution = ExecutionConfig(
    execution_mode=ExecutionMode.WATCHER,
    invocation_mode=InvocationMode.SUBPROCESS,
    dbt_executable_path=DBT_EXECUTABLE,
)
_render = RenderConfig(load_method=LoadMode.DBT_MANIFEST)


@dag(
    schedule=[BRONZE],
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    # Watcher tasks are cheap, but keep the slot count modest on a laptop.
    max_active_tasks=8,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["dbt", "silver", "gold", "cosmos"],
    doc_md=__doc__,
)
def dbt_lakehouse() -> None:
    """Cosmos task group for the whole dbt project, then DuckLake housekeeping."""
    transform = DbtTaskGroup(
        group_id="dbt",
        project_config=_project,
        profile_config=_profile,
        execution_config=_execution,
        render_config=_render,
    )

    housekeeping = BashOperator(
        task_id="ducklake_maintenance",
        bash_command=(
            f"{DBT_EXECUTABLE} run-operation ducklake_maintenance --args '{{days: 7}}' "
            f"--project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"
        ),
        outlets=[GOLD],
    )

    transform >> housekeeping


dbt_lakehouse()

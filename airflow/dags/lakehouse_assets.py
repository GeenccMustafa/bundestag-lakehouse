"""Airflow Assets shared between the lakehouse DAGs.

An Asset is a named piece of data. A task that lists it in `outlets` emits an asset event when
it succeeds, and DAGs scheduled on the asset run after that event (data-aware scheduling).
"""

from airflow.sdk import Asset

BRONZE = Asset(name="bronze", uri="s3://lakehouse/bronze/")
"""Raw DIP pages; updated when a dip_ingestion run has loaded every entity."""

GOLD = Asset(name="gold", uri="s3://lakehouse/gold/")
"""Star schema; updated when dbt_lakehouse has built and tested every model."""

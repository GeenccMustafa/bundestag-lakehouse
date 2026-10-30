# Airflow + Cosmos, with dbt in its own virtualenv so dbt's dependencies never clash with
# Airflow's. dbt versions are pinned (with hashes) by dbt/requirements.txt, exported from
# uv.lock, so Airflow runs exactly the dbt the repo is tested with.
FROM apache/airflow:3.3.2-python3.12

ARG AIRFLOW_VERSION=3.3.2
ARG COSMOS_VERSION=1.15.1

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

# Cosmos goes into Airflow's own environment. Airflow's documented way to extend the image is
# pip with Airflow's constraints file (and Airflow pinned), so nothing Airflow relies on moves.
RUN pip install --no-cache-dir \
        "apache-airflow==${AIRFLOW_VERSION}" \
        "astronomer-cosmos==${COSMOS_VERSION}" \
        --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"

# dbt in an isolated venv; Cosmos calls /opt/airflow/dbt-venv/bin/dbt as a subprocess.
COPY dbt/requirements.txt /tmp/dbt-requirements.txt
RUN uv venv /opt/airflow/dbt-venv --python "$(command -v python)" \
    && uv pip install --python /opt/airflow/dbt-venv/bin/python \
        --require-hashes --no-deps -r /tmp/dbt-requirements.txt \
    && /opt/airflow/dbt-venv/bin/dbt --version

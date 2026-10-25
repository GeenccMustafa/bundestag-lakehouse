-- Idempotent: creates (or updates the password of) the DuckLake catalog role and database.
-- Run by the `postgres-init` Compose service with psql variables :ducklake_user,
-- :ducklake_password and :ducklake_db. Separate from Airflow's role so neither can touch
-- the other's metadata.
SELECT format('CREATE ROLE %I LOGIN', :'ducklake_user')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'ducklake_user')
\gexec

ALTER ROLE :"ducklake_user" WITH LOGIN PASSWORD :'ducklake_password';

SELECT format('CREATE DATABASE %I OWNER %I', :'ducklake_db', :'ducklake_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'ducklake_db')
\gexec

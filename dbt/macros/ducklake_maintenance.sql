{#-
  Every `dbt build` writes new Parquet files; DuckLake keeps the old ones so earlier snapshots
  stay queryable (time travel). This expires snapshots older than `days` and deletes the files
  nothing references any more.

    uv run --env-file .env dbt run-operation ducklake_maintenance --args '{days: 7}'
-#}
{% macro ducklake_maintenance(days=7) %}
  {% set catalog = target.database %}
  {% set sql %}
    call ducklake_expire_snapshots('{{ catalog }}', older_than => now() - interval ({{ days }}) day);
    call ducklake_cleanup_old_files('{{ catalog }}', cleanup_all => true);
  {% endset %}
  {% do run_query(sql) %}
  {% do log("DuckLake '" ~ catalog ~ "': expired snapshots older than " ~ days ~ " days and removed unreferenced files", info=true) %}
{% endmacro %}

{#-
  Table materialization for DuckLake: one atomic `CREATE OR REPLACE TABLE`.

  dbt's default `table` materialization builds `<name>__dbt_tmp` and renames it. DuckLake keeps
  a table's Parquet files in the folder named at creation time, so every table would live under
  `.../<name>__dbt_tmp/` in object storage. DuckLake replaces tables transactionally (a new
  snapshot), so the temp-and-rename dance buys nothing here.
-#}
{% materialization ducklake_table, adapter="duckdb" %}
  {%- set target_relation = this.incorporate(type="table") -%}
  {%- set existing_relation = load_cached_relation(this) -%}

  {{ run_hooks(pre_hooks, inside_transaction=False) }}
  {{ run_hooks(pre_hooks, inside_transaction=True) }}

  {%- if existing_relation is not none and existing_relation.type != "table" -%}
    {{ drop_relation_if_exists(existing_relation) }}
  {%- endif -%}

  {% call statement("main") -%}
    create or replace table {{ target_relation }} as (
      {{ sql }}
    )
  {%- endcall %}

  {{ run_hooks(post_hooks, inside_transaction=True) }}
  {{ adapter.commit() }}
  {% do persist_docs(target_relation, model) %}
  {{ run_hooks(post_hooks, inside_transaction=False) }}

  {{ return({"relations": [target_relation]}) }}
{% endmaterialization %}

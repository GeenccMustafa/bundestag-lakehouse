{#- One row per document version found in Bronze, with lineage columns.
    Each Bronze file is one API page: {"numFound", "cursor", "documents": [...]}. -#}
{% macro dip_documents(source_table) %}
    select
        doc,
        doc ->> 'id' as _id,
        cast(doc ->> 'aktualisiert' as timestamptz) as aktualisiert_at,
        dt as _bronze_dt,
        run as _bronze_run,
        filename as _bronze_file
    from {{ source('dip', source_table) }},
        unnest(from_json(json -> 'documents', '["JSON"]')) as t(doc)
{% endmacro %}


{#- Keep only the newest version of each record. Ties (same `aktualisiert` fetched twice,
    e.g. through the ingestion overlap) are broken by the newest Bronze file. -#}
{% macro latest_version(relation, key) %}
    select *
    from {{ relation }}
    qualify row_number() over (
        partition by {{ key }}
        order by aktualisiert_at desc, _bronze_dt desc, _bronze_file desc
    ) = 1
{% endmacro %}


{#- JSON array of strings -> VARCHAR[] (NULL stays NULL). -#}
{% macro json_strings(expr) %}
    from_json({{ expr }}, '["VARCHAR"]')
{% endmacro %}

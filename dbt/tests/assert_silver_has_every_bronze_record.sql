-- Deduplication must not lose records: every id seen in Bronze appears exactly once in
-- Silver, and Silver holds its newest version. Returns offending ids per entity.
{% set entities = {
    'vorgang': 'vorgang_id',
    'vorgangsposition': 'vorgangsposition_id',
    'drucksache': 'drucksache_id',
    'plenarprotokoll': 'plenarprotokoll_id',
    'aktivitaet': 'aktivitaet_id',
    'person': 'person_id',
} %}

{% for entity, key in entities.items() %}
select
    '{{ entity }}' as entity,
    b.{{ key }} as id,
    b.max_aktualisiert_at,
    s.aktualisiert_at as silver_aktualisiert_at
from (
    select {{ key }}, max(aktualisiert_at) as max_aktualisiert_at
    from {{ ref('base_dip__' ~ entity) }}
    group by 1
) as b
left join {{ ref('stg_dip__' ~ entity) }} as s using ({{ key }})
where s.aktualisiert_at is distinct from b.max_aktualisiert_at
{% if not loop.last %}union all{% endif %}
{% endfor %}

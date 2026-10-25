-- Ministries (Ressorts) responsible for a Drucksache; one is usually lead (federführend).
with latest as ({{ latest_version(ref('base_dip__drucksache'), 'drucksache_id') }})

select
    latest.drucksache_id,
    r ->> 'titel' as ressort,
    coalesce(cast(r ->> 'federfuehrend' as boolean), false) as is_federfuehrend
from latest,
    unnest(from_json(doc -> 'ressort', '["JSON"]')) as t(r)

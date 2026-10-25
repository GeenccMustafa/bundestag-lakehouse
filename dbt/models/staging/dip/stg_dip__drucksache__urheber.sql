-- Originators of a Drucksache (Bundesregierung, a Fraktion, a Land, ...).
with latest as ({{ latest_version(ref('base_dip__drucksache'), 'drucksache_id') }})

select
    latest.drucksache_id,
    u ->> 'bezeichnung' as urheber_kuerzel,
    u ->> 'titel' as urheber,
    coalesce(cast(u ->> 'einbringer' as boolean), false) as is_einbringer
from latest,
    unnest(from_json(doc -> 'urheber', '["JSON"]')) as t(u)

-- Bridge: which Vorgänge a Drucksache belongs to.
with latest as ({{ latest_version(ref('base_dip__drucksache'), 'drucksache_id') }})

select distinct
    latest.drucksache_id,
    v ->> 'id' as vorgang_id
from latest,
    unnest(from_json(doc -> 'vorgangsbezug', '["JSON"]')) as t(v)

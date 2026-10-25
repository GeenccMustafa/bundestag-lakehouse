-- Bridge: which Vorgänge an Aktivität belongs to.
with latest as ({{ latest_version(ref('base_dip__aktivitaet'), 'aktivitaet_id') }})

select distinct
    latest.aktivitaet_id,
    v ->> 'id' as vorgang_id,
    v ->> 'vorgangsposition' as vorgangsposition
from latest,
    unnest(from_json(doc -> 'vorgangsbezug', '["JSON"]')) as t(v)

-- Latest version of each aktivitaet (nested arrays are flattened into child models).
with latest as ({{ latest_version(ref('base_dip__aktivitaet'), 'aktivitaet_id') }})

select * exclude (doc)
from latest

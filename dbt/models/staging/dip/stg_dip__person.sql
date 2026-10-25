-- Latest version of each person (nested arrays are flattened into child models).
with latest as ({{ latest_version(ref('base_dip__person'), 'person_id') }})

select * exclude (doc)
from latest

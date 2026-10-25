-- Latest version of each drucksache (nested arrays are flattened into child models).
with latest as ({{ latest_version(ref('base_dip__drucksache'), 'drucksache_id') }})

select * exclude (doc)
from latest

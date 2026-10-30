-- One row per federal ministry (Ressort), from Drucksache responsibilities and government
-- roles of persons.
with names as (
    select ressort from {{ ref('stg_dip__drucksache__ressort') }}
    union
    select ressort from {{ ref('stg_dip__person__rolle') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['ressort']) }} as ressort_key,
    ressort as ressort_name
from names
where ressort is not null

union all

select {{ unknown_key() }}, 'Unbekannt'

-- One row per parliamentary group (Fraktion), in DIP's spelling. Collected from every place
-- a Fraktion appears: activity titles, person roles and Drucksache originators.
with names as (
    select fraktion from {{ ref('int_aktivitaet__akteur') }}
    union
    select fraktion from {{ ref('stg_dip__person__rolle') }}
    union
    select fraktion from {{ ref('int_drucksache__urheber') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['fraktion']) }} as fraktion_key,
    fraktion as fraktion_name,
    fraktion = 'fraktionslos' as is_fraktionslos
from names
where fraktion is not null

union all

select {{ unknown_key() }}, 'Unbekannt', false

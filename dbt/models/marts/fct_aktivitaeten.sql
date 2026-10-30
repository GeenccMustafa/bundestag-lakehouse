-- Grain: one row per Aktivität (speech, question, motion signature ...) of a person.
-- Incremental: only activities changed since the last run (minus a 3-day lookback for late
-- updates) are re-processed and merged on aktivitaet_id. `--full-refresh` rebuilds it all
-- and must give the same result.
--
-- Two point-in-time joins:
--   person_key   -> the dim_person version valid on the activity date (SCD2)
--   fraktion_key -> the Fraktion DIP printed on the activity itself
{{
    config(
        materialized='incremental',
        unique_key='aktivitaet_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

with aktivitaeten as (
    select * from {{ ref('stg_dip__aktivitaet') }}
    {% if is_incremental() %}
        where aktualisiert_at > (
            select coalesce(max(aktualisiert_at), timestamptz '1900-01-01') - interval 3 day
            from {{ this }}
        )
    {% endif %}
)

select
    a.aktivitaet_id,
    {{ date_key('a.datum') }} as date_key,
    coalesce(p.person_key, {{ unknown_key() }}) as person_key,
    coalesce(f.fraktion_key, {{ unknown_key() }}) as fraktion_key,
    a.aktivitaetsart,
    a.dokumentart,
    k.akteur_rolle,
    a.wahlperiode,
    a.vorgangsbezug_anzahl,
    a.aktualisiert_at
from aktivitaeten as a
inner join {{ ref('int_aktivitaet__akteur') }} as k using (aktivitaet_id)
left join {{ ref('dim_person') }} as p
    on p.person_id = a.person_id
    and a.datum >= p.valid_from
    and a.datum < p.valid_to
left join {{ ref('dim_fraktion') }} as f on f.fraktion_name = k.fraktion

-- Grain: one row per Drucksache (printed paper).
-- Answers e.g. "which ministry is responsible for how many papers" (ressort_key = the lead,
-- federführend, ministry) and "who files papers" (primary originator type and Fraktion).
with drucksachen as (
    select * from {{ ref('stg_dip__drucksache') }}
),

lead_ressort as (
    select drucksache_id, ressort
    from {{ ref('stg_dip__drucksache__ressort') }}
    where is_federfuehrend
    -- Rarely more than one lead ministry; take one deterministically.
    qualify row_number() over (partition by drucksache_id order by ressort) = 1
),

urheber as (
    select
        drucksache_id,
        count(*) as urheber_anzahl,
        arg_min(urheber_typ, urheber_rang) as urheber_typ,
        -- First Fraktion alphabetically when several file a paper together.
        min(fraktion) as fraktion
    from {{ ref('int_drucksache__urheber') }}
    group by drucksache_id
)

select
    d.drucksache_id,
    d.dokumentnummer,
    {{ date_key('d.datum') }} as date_key,
    coalesce(r.ressort_key, {{ unknown_key() }}) as ressort_key,
    coalesce(f.fraktion_key, {{ unknown_key() }}) as fraktion_key,
    d.drucksachetyp,
    d.herausgeber,
    d.wahlperiode,
    coalesce(u.urheber_typ, 'Unbekannt') as urheber_typ,
    coalesce(u.urheber_anzahl, 0) as urheber_anzahl,
    d.autoren_anzahl,
    d.vorgangsbezug_anzahl,
    d.aktualisiert_at
from drucksachen as d
left join lead_ressort as lr using (drucksache_id)
left join {{ ref('dim_ressort') }} as r on r.ressort_name = lr.ressort
left join urheber as u using (drucksache_id)
left join {{ ref('dim_fraktion') }} as f on f.fraktion_name = u.fraktion

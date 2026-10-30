-- One row per person with their current descriptive attributes: the input of the SCD2
-- snapshot. Names come from the person entity when we have it, otherwise from the latest
-- Aktivität that mentions the person; the current Fraktion is the one on their most recent
-- activity as MdB.
with from_person as (
    -- The person entity's own title also carries role and Fraktion ("Jan Krampe, MdB,
    -- DIE LINKE"); build a plain name instead so both sources look the same.
    select person_id, vorname, nachname, trim(concat_ws(' ', vorname, nachname)) as anzeigename
    from {{ ref('stg_dip__person') }}
),

latest_activity as (
    select
        a.person_id,
        k.akteur_name,
        k.akteur_rolle
    from {{ ref('stg_dip__aktivitaet') }} as a
    inner join {{ ref('int_aktivitaet__akteur') }} as k using (aktivitaet_id)
    qualify row_number() over (
        partition by a.person_id order by a.datum desc, a.aktualisiert_at desc
    ) = 1
),

latest_fraktion as (
    select
        a.person_id,
        k.fraktion
    from {{ ref('stg_dip__aktivitaet') }} as a
    inner join {{ ref('int_aktivitaet__akteur') }} as k using (aktivitaet_id)
    where k.fraktion is not null
    qualify row_number() over (
        partition by a.person_id order by a.datum desc, a.aktualisiert_at desc
    ) = 1
),

ids as (
    select person_id from from_person
    union
    select person_id from latest_activity
)

select
    ids.person_id,
    coalesce(p.anzeigename, act.akteur_name) as anzeigename,
    p.vorname,
    p.nachname,
    act.akteur_rolle as aktuelle_rolle,
    f.fraktion as aktuelle_fraktion,
    case when p.person_id is not null then 'person' else 'aktivitaet' end as quelle
from ids
left join from_person as p using (person_id)
left join latest_activity as act using (person_id)
left join latest_fraktion as f using (person_id)

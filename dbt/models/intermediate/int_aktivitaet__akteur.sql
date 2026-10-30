-- Who performed an Aktivität, as DIP printed it at the time, e.g.
--   "Dr. Götz Frömming, MdB, AfD"
--   "Karin Prien, Bundesmin., Bundesministerium für Bildung, ..."
--   "Timon Gremmels, MdBR (Staatsminister, ...), Hessen"
-- For members of the Bundestag (MdB) the third part is their Fraktion on that day, which is
-- exactly the point-in-time value the activity fact needs.
with parts as (
    select
        aktivitaet_id,
        person_id,
        string_split(titel, ', ') as part
    from {{ ref('stg_dip__aktivitaet') }}
)

select
    aktivitaet_id,
    person_id,
    part[1] as akteur_name,
    case
        when part[2] = 'MdB' then 'MdB'
        when part[2] like 'MdBR%' or part[2] like 'Stellv. MdBR%' then 'Bundesrat'
        else part[2]
    end as akteur_rolle,
    case when part[2] = 'MdB' then nullif(part[3], '') end as fraktion
from parts

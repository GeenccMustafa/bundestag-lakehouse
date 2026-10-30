-- Grain: one row per Vorgang (legislative or parliamentary procedure).
-- Answers "how long does a procedure take": dauer_tage runs from the first known step to
-- promulgation (Verkündung). Steps older than our ingestion window are missing, so the start
-- is a lower bound; dauer_tage is NULL until a procedure is promulgated.
with vorgaenge as (
    select * from {{ ref('stg_dip__vorgang') }}
),

verlauf as (
    select * from {{ ref('int_vorgang__verlauf') }}
)

select
    v.vorgang_id,
    v.vorgangstyp,
    v.beratungsstand,
    v.wahlperiode,
    coalesce(v.initiative[1], 'Unbekannt') as initiative,
    {{ date_key('vl.erste_position_am') }} as start_date_key,
    {{ date_key('v.verkuendet_am') }} as verkuendet_date_key,
    {{ date_key('v.inkrafttreten_am') }} as inkrafttreten_date_key,
    coalesce(vl.positionen_anzahl, 0) as positionen_anzahl,
    case
        when v.verkuendet_am is not null and vl.erste_position_am is not null
            then date_diff('day', vl.erste_position_am, v.verkuendet_am)
    end as dauer_tage,
    v.verkuendet_am is not null as is_verkuendet,
    v.beratungsstand in (
        'Verkündet', 'Abgeschlossen', 'Beantwortet', 'Abgelehnt', 'Angenommen',
        'Verabschiedet', 'Erledigt durch Ablauf der Wahlperiode'
    ) as is_abgeschlossen,
    v.aktualisiert_at
from vorgaenge as v
left join verlauf as vl using (vorgang_id)

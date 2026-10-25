with documents as ({{ dip_documents('aktivitaet') }})

select
    _id as aktivitaet_id,
    doc ->> 'person_id' as person_id,
    doc ->> 'aktivitaetsart' as aktivitaetsart,
    doc ->> 'titel' as titel,
    doc ->> 'dokumentart' as dokumentart,
    cast(doc ->> 'datum' as date) as datum,
    cast(doc ->> 'wahlperiode' as integer) as wahlperiode,
    cast(doc ->> 'vorgangsbezug_anzahl' as integer) as vorgangsbezug_anzahl,
    doc -> 'fundstelle' ->> 'id' as fundstelle_dokument_id,
    doc -> 'fundstelle' ->> 'dokumentnummer' as fundstelle_dokumentnummer,
    doc,
    aktualisiert_at,
    _bronze_dt,
    _bronze_run,
    _bronze_file
from documents

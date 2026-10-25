with documents as ({{ dip_documents('drucksache') }})

select
    _id as drucksache_id,
    doc ->> 'dokumentnummer' as dokumentnummer,
    doc ->> 'drucksachetyp' as drucksachetyp,
    doc ->> 'titel' as titel,
    doc ->> 'herausgeber' as herausgeber,
    cast(doc ->> 'datum' as date) as datum,
    cast(doc ->> 'wahlperiode' as integer) as wahlperiode,
    cast(doc ->> 'autoren_anzahl' as integer) as autoren_anzahl,
    cast(doc ->> 'vorgangsbezug_anzahl' as integer) as vorgangsbezug_anzahl,
    doc -> 'fundstelle' ->> 'pdf_url' as pdf_url,
    doc,
    aktualisiert_at,
    _bronze_dt,
    _bronze_run,
    _bronze_file
from documents

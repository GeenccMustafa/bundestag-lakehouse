with documents as ({{ dip_documents('plenarprotokoll') }})

select
    _id as plenarprotokoll_id,
    doc ->> 'dokumentnummer' as dokumentnummer,
    doc ->> 'titel' as titel,
    doc ->> 'herausgeber' as herausgeber,
    cast(doc ->> 'datum' as date) as datum,
    cast(doc ->> 'wahlperiode' as integer) as wahlperiode,
    cast(doc ->> 'vorgangsbezug_anzahl' as integer) as vorgangsbezug_anzahl,
    doc -> 'fundstelle' ->> 'pdf_url' as pdf_url,
    aktualisiert_at,
    _bronze_dt,
    _bronze_run,
    _bronze_file
from documents

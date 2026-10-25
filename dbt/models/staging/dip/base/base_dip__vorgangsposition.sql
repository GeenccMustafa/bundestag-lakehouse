with documents as ({{ dip_documents('vorgangsposition') }})

select
    _id as vorgangsposition_id,
    doc ->> 'vorgang_id' as vorgang_id,
    doc ->> 'vorgangsposition' as vorgangsposition,
    doc ->> 'vorgangstyp' as vorgangstyp,
    doc ->> 'titel' as titel,
    doc ->> 'dokumentart' as dokumentart,
    doc ->> 'zuordnung' as zuordnung,
    cast(doc ->> 'datum' as date) as datum,
    cast(doc ->> 'gang' as boolean) as is_gang,
    cast(doc ->> 'nachtrag' as boolean) as is_nachtrag,
    cast(doc ->> 'aktivitaet_anzahl' as integer) as aktivitaet_anzahl,
    doc -> 'fundstelle' ->> 'id' as fundstelle_dokument_id,
    aktualisiert_at,
    _bronze_dt,
    _bronze_run,
    _bronze_file
from documents

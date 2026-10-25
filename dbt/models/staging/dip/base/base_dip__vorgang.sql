with documents as ({{ dip_documents('vorgang') }})

select
    _id as vorgang_id,
    cast(doc ->> 'wahlperiode' as integer) as wahlperiode,
    doc ->> 'vorgangstyp' as vorgangstyp,
    doc ->> 'titel' as titel,
    doc ->> 'abstract' as abstract,
    doc ->> 'beratungsstand' as beratungsstand,
    cast(doc ->> 'datum' as date) as datum,
    doc ->> 'gesta' as gesta_ordnungsnummer,
    {{ json_strings("doc -> 'initiative'") }} as initiative,
    {{ json_strings("doc -> 'sachgebiet'") }} as sachgebiet,
    aktualisiert_at,
    _bronze_dt,
    _bronze_run,
    _bronze_file
from documents

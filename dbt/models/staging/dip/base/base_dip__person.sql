with documents as ({{ dip_documents('person') }})

select
    _id as person_id,
    doc ->> 'vorname' as vorname,
    doc ->> 'nachname' as nachname,
    doc ->> 'titel' as anzeigename,
    cast(doc ->> 'basisdatum' as date) as basisdatum,
    cast(doc ->> 'datum' as date) as datum,
    from_json(doc -> 'wahlperiode', '["INTEGER"]') as wahlperioden,
    {{ json_strings("doc -> 'fraktion'") }} as fraktionen,
    {{ json_strings("doc -> 'funktion'") }} as funktionen,
    doc,
    aktualisiert_at,
    _bronze_dt,
    _bronze_run,
    _bronze_file
from documents

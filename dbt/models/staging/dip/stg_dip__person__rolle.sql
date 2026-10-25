-- Roles of a person: Fraktion membership or a government office, per Wahlperiode.
-- One input role may cover several Wahlperioden; we emit one row per Wahlperiode.
with latest as ({{ latest_version(ref('base_dip__person'), 'person_id') }}),

roles as (
    select
        latest.person_id,
        role,
        row_number() over (partition by latest.person_id) as rolle_nr
    from latest,
        unnest(from_json(doc -> 'person_roles', '["JSON"]')) as t(role)
)

select
    person_id,
    rolle_nr,
    wp.wahlperiode,
    role ->> 'fraktion' as fraktion,
    role ->> 'funktion' as funktion,
    role ->> 'ressort_titel' as ressort,
    role ->> 'bundesland' as bundesland,
    role ->> 'vorname' as vorname,
    role ->> 'nachname' as nachname
from roles,
    unnest(from_json(role -> 'wahlperiode_nummer', '["INTEGER"]')) as wp(wahlperiode)

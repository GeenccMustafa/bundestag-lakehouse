-- SCD Type 2 person dimension: one row per person and version, built on the snp_person
-- snapshot. Facts join on the version valid at the fact's date:
--     fact.datum >= valid_from and fact.datum < valid_to
-- The snapshot only knows history from its first run on, so each person's first version is
-- back-dated to 1900-01-01: older facts then get the earliest known attributes instead of the
-- unknown member.
with versions as (
    select
        *,
        row_number() over (partition by person_id order by dbt_valid_from) as version_nr
    from {{ ref('snp_person') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['person_id', 'dbt_valid_from']) }} as person_key,
    person_id,
    anzeigename,
    vorname,
    nachname,
    aktuelle_rolle as rolle,
    aktuelle_fraktion as fraktion,
    quelle,
    version_nr,
    case
        when version_nr = 1 then timestamp '1900-01-01'
        else cast(dbt_valid_from as timestamp)
    end as valid_from,
    coalesce(cast(dbt_valid_to as timestamp), timestamp '9999-12-31') as valid_to,
    dbt_valid_to is null as is_current
from versions

union all

select
    {{ unknown_key() }}, null, 'Unbekannt', null, null, null, null, null, 1,
    timestamp '1900-01-01', timestamp '9999-12-31', true

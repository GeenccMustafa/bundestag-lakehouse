-- Life cycle of a Vorgang from its steps (Vorgangspositionen): first and last step, number of
-- steps. Only steps we hold in Bronze count, so for procedures that started before our
-- ingestion window `erste_position_am` is a lower bound, not the true start.
select
    vorgang_id,
    min(datum) as erste_position_am,
    max(datum) as letzte_position_am,
    count(*) as positionen_anzahl
from {{ ref('stg_dip__vorgangsposition') }}
group by vorgang_id

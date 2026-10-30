-- How long do procedures take until promulgation, by type? Starts are lower bounds while
-- Bronze does not hold the full history of every procedure.
select
    vorgangstyp,
    count(*) as verkuendet,
    round(avg(dauer_tage), 1) as avg_tage,
    median(dauer_tage) as median_tage,
    max(dauer_tage) as max_tage
from {{ ref('fct_vorgaenge') }}
where dauer_tage is not null
group by 1
order by verkuendet desc

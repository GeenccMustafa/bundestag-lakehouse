-- On which weekdays are Drucksachen published, and who files them?
select
    d.wochentag,
    count(*) as drucksachen,
    count(*) filter (where f.urheber_typ = 'Bundesregierung') as bundesregierung,
    count(*) filter (where f.urheber_typ = 'Fraktion') as fraktionen
from {{ ref('fct_drucksachen') }} as f
inner join {{ ref('dim_date') }} as d using (date_key)
group by d.wochentag_nr, d.wochentag
order by d.wochentag_nr

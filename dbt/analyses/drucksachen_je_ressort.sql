-- Which ministry is lead-responsible (federführend) for how many Drucksachen, by type?
select
    r.ressort_name as ressort,
    count(*) as drucksachen,
    count(*) filter (where f.drucksachetyp = 'Antwort') as antworten,
    count(*) filter (where f.drucksachetyp = 'Gesetzentwurf') as gesetzentwuerfe
from {{ ref('fct_drucksachen') }} as f
inner join {{ ref('dim_ressort') }} as r using (ressort_key)
where r.ressort_name != 'Unbekannt'
group by 1
order by drucksachen desc

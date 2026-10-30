-- How active is each Fraktion, per member: activities, speeches and Kleine Anfragen.
select
    fr.fraktion_name as fraktion,
    count(*) as aktivitaeten,
    count(distinct p.person_id) as aktive_abgeordnete,
    round(count(*) / count(distinct p.person_id), 1) as aktivitaeten_je_abgeordnete,
    count(*) filter (where f.aktivitaetsart like 'Rede%') as reden,
    count(*) filter (where f.aktivitaetsart = 'Kleine Anfrage') as kleine_anfragen
from {{ ref('fct_aktivitaeten') }} as f
inner join {{ ref('dim_fraktion') }} as fr using (fraktion_key)
inner join {{ ref('dim_person') }} as p using (person_key)
where fr.fraktion_name != 'Unbekannt'
group by 1
order by aktivitaeten desc

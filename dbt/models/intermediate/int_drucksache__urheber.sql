-- Originators of a Drucksache, classified. A paper can have several originators (e.g. two
-- Fraktionen, or several Länder); `urheber_rang` orders the types so the fact can pick one
-- primary originator.
select
    u.drucksache_id,
    u.urheber,
    u.is_einbringer,
    case
        when u.urheber = 'Bundesregierung' then 'Bundesregierung'
        when u.urheber like 'Fraktion %' then 'Fraktion'
        when u.urheber = 'Bundesrat' or l.bundesland is not null then 'Bundesrat/Land'
        when u.urheber like 'Ausschuss%' or u.urheber like '%ausschuss' then 'Ausschuss'
        when u.urheber like 'Europäische%' then 'EU'
        else 'Sonstige'
    end as urheber_typ,
    case
        when u.urheber = 'Bundesregierung' then 1
        when u.urheber like 'Fraktion %' then 2
        when u.urheber = 'Bundesrat' or l.bundesland is not null then 3
        when u.urheber like 'Ausschuss%' or u.urheber like '%ausschuss' then 4
        when u.urheber like 'Europäische%' then 5
        else 6
    end as urheber_rang,
    {{ fraktion_from_urheber('u.urheber') }} as fraktion
from {{ ref('stg_dip__drucksache__urheber') }} as u
left join {{ ref('bundeslaender') }} as l on l.bundesland = u.urheber

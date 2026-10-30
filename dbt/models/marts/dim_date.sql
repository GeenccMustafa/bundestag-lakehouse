-- One row per calendar day from the first Bundestag (1949) to two years ahead, plus the
-- unknown member (-1). Generated, not derived from data, so every fact date has a match.
with spine as (
    select cast(d as date) as datum
    from generate_series(
        timestamp '1949-01-01', cast(current_date + interval 2 year as timestamp), interval 1 day
    ) as t(d)
)

select
    {{ date_key('s.datum') }} as date_key,
    s.datum,
    year(s.datum) as jahr,
    quarter(s.datum) as quartal,
    month(s.datum) as monat,
    strftime(s.datum, '%Y-%m') as jahr_monat,
    weekofyear(s.datum) as kalenderwoche,
    isodow(s.datum) as wochentag_nr,
    ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'][
        isodow(s.datum)
    ] as wochentag,
    isodow(s.datum) >= 6 as is_wochenende,
    w.wahlperiode
from spine as s
left join {{ ref('wahlperioden') }} as w
    on s.datum between w.beginn and coalesce(w.ende, date '9999-12-31')

union all

select
    -1, null, null, null, null, null, null, null, 'Unbekannt', null, null

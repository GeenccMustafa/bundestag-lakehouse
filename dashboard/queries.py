"""SQL the dashboard runs against the Gold star schema.

Every function takes a DuckDB connection with the lake attached as ``lake`` (see
:mod:`dashboard.lake`) and returns a pandas DataFrame, so the queries can be tested without
Streamlit. Filters are bound as parameters, never formatted into the SQL.

The facts are always joined to their dimensions through surrogate keys. Unknown members (key
``'-1'``, date_key ``-1``) are kept in counts but left out of per-dimension rankings, where
"Unbekannt" would only crowd out the known values.
"""

from dataclasses import dataclass
from datetime import date

import duckdb
import pandas as pd

UNKNOWN_KEY = "-1"


@dataclass(frozen=True)
class Filters:
    """What the sidebar selected: an inclusive date range, optionally one Wahlperiode."""

    start: date
    end: date
    wahlperiode: int | None = None

    def params(self) -> list[int | None]:
        """Return ``[start_key, end_key, wahlperiode]`` for the ``_WHERE`` clause."""
        return [_date_key(self.start), _date_key(self.end), self.wahlperiode]


def _date_key(d: date) -> int:
    return d.year * 10_000 + d.month * 100 + d.day


def _where(key: str | None = "f.date_key") -> str:
    # Filter on a fact's date key and Wahlperiode; $1..$3 are Filters.params(). Numbered
    # parameters can be repeated, so one parameter list serves every subquery. key=None
    # filters on the Wahlperiode only (the range stays bound but unused).
    dates = f"{key} between $1 and $2" if key else "$1::integer <= $2::integer"
    return f"{dates} and ($3::integer is null or f.wahlperiode = $3)"


def _df(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    return con.execute(sql, params or []).df()


def date_bounds(
    con: duckdb.DuckDBPyConnection, wahlperiode: int | None = None
) -> tuple[date, date]:
    """Return the first and last day any fact has, optionally within one Wahlperiode.

    This is the range the date picker offers. With no facts at all, both ends are today.
    """
    sql = """
        with keys as (
            select date_key, wahlperiode from lake.gold.fct_drucksachen
            union all select date_key, wahlperiode from lake.gold.fct_aktivitaeten
            union all select start_date_key, wahlperiode from lake.gold.fct_vorgaenge
        )
        select min(d.datum), max(d.datum)
        from keys as k
        join lake.gold.dim_date as d using (date_key)
        where d.date_key <> -1 and ($1::integer is null or k.wahlperiode = $1)
    """
    first, last = con.execute(sql, [wahlperiode]).fetchone()
    if first is None:
        today = date.today()
        return today, today
    return first, last


def wahlperioden(con: duckdb.DuckDBPyConnection) -> list[int]:
    """Return the Wahlperioden that occur in the facts, newest first."""
    sql = """
        select distinct wahlperiode from (
            select wahlperiode from lake.gold.fct_drucksachen
            union all select wahlperiode from lake.gold.fct_aktivitaeten
            union all select wahlperiode from lake.gold.fct_vorgaenge
        )
        where wahlperiode is not null
        order by wahlperiode desc
    """
    return [row[0] for row in con.execute(sql).fetchall()]


def freshness(con: duckdb.DuckDBPyConnection) -> dict:
    """Describe how current the lake is.

    Returns:
        ``snapshot_id`` and ``snapshot_time`` of the latest DuckLake commit (the last dbt
        write) and ``source_updated_at``, the newest DIP ``aktualisiert`` timestamp in Gold.
    """
    snapshot_id, snapshot_time = con.execute(
        "select snapshot_id, snapshot_time from lake.snapshots() order by snapshot_id desc limit 1"
    ).fetchone()
    (source_updated_at,) = con.execute(
        """
        select max(aktualisiert_at) from (
            select aktualisiert_at from lake.gold.fct_drucksachen
            union all select aktualisiert_at from lake.gold.fct_aktivitaeten
            union all select aktualisiert_at from lake.gold.fct_vorgaenge
        )
        """
    ).fetchone()
    return {
        "snapshot_id": snapshot_id,
        "snapshot_time": snapshot_time,
        "source_updated_at": source_updated_at,
    }


def kpis(con: duckdb.DuckDBPyConnection, filters: Filters) -> dict[str, int]:
    """Count the facts in the selected range.

    Returns:
        ``drucksachen``, ``vorgaenge`` (Wahlperiode only, see vorgaenge_je_typ),
        ``aktivitaeten`` and ``personen`` (distinct known persons with an activity).
    """
    sql = f"""
        select
            (select count(*) from lake.gold.fct_drucksachen as f where {_where()}),
            (select count(*) from lake.gold.fct_vorgaenge as f where {_where(None)}),
            (select count(*) from lake.gold.fct_aktivitaeten as f where {_where()}),
            (select count(distinct p.person_id)
                from lake.gold.fct_aktivitaeten as f
                join lake.gold.dim_person as p using (person_key)
                where {_where()} and f.person_key <> '{UNKNOWN_KEY}')
    """
    row = con.execute(sql, filters.params()).fetchone()
    return dict(zip(("drucksachen", "vorgaenge", "aktivitaeten", "personen"), row, strict=True))


def drucksachen_je_ressort(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    """Drucksachen per lead (federführend) ministry, largest first. Columns: ressort, anzahl."""
    sql = f"""
        select r.ressort_name as ressort, count(*) as anzahl
        from lake.gold.fct_drucksachen as f
        join lake.gold.dim_ressort as r using (ressort_key)
        where {_where()} and f.ressort_key <> '{UNKNOWN_KEY}'
        group by all
        order by anzahl desc, ressort
    """
    return _df(con, sql, filters.params())


def aktivitaeten_je_fraktion(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    """Activities per Fraktion at the time of the activity, largest first.

    Columns: fraktion, anzahl, personen (distinct persons who were active).
    """
    sql = f"""
        select
            fr.fraktion_name as fraktion,
            count(*) as anzahl,
            count(distinct p.person_id) as personen
        from lake.gold.fct_aktivitaeten as f
        join lake.gold.dim_fraktion as fr using (fraktion_key)
        join lake.gold.dim_person as p using (person_key)
        where {_where()} and f.fraktion_key <> '{UNKNOWN_KEY}'
        group by all
        order by anzahl desc, fraktion
    """
    return _df(con, sql, filters.params())


def zeit_grain(filters: Filters) -> str:
    """Pick the time bucket for a range: days up to a quarter, weeks up to two years, else months.

    Keeps a time series at roughly 15-100 bars, whatever range is selected.
    """
    days = (filters.end - filters.start).days
    if days <= 92:
        return "day"
    return "week" if days <= 730 else "month"


def aktivitaeten_im_zeitverlauf(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    """Activities per day, week or month (see :func:`zeit_grain`).

    Buckets between the first and last active one are all present, empty ones as 0, so gaps are
    visible. Columns: periode (first day of the bucket), anzahl.
    """
    grain = zeit_grain(filters)  # one of three literals, safe to splice into the SQL
    sql = f"""
        with counts as (
            select date_trunc('{grain}', d.datum) as periode, count(*) as anzahl
            from lake.gold.fct_aktivitaeten as f
            join lake.gold.dim_date as d using (date_key)
            where {_where()}
            group by all
        ),
        spine as (
            select unnest(generate_series(min(periode), max(periode), interval 1 {grain}))
                as periode
            from counts
        )
        select cast(s.periode as date) as periode, coalesce(c.anzahl, 0) as anzahl
        from spine as s
        left join counts as c using (periode)
        order by s.periode
    """
    return _df(con, sql, filters.params())


def aktivitaeten_je_art(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    """Activities per kind (speech, written question ...), largest first.

    Columns: aktivitaetsart, anzahl.
    """
    sql = f"""
        select coalesce(f.aktivitaetsart, 'Unbekannt') as aktivitaetsart, count(*) as anzahl
        from lake.gold.fct_aktivitaeten as f
        where {_where()}
        group by all
        order by anzahl desc, aktivitaetsart
    """
    return _df(con, sql, filters.params())


def drucksachen_je_wochentag(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    """Drucksachen per weekday, Monday first, all seven days present.

    Columns: wochentag_nr, wochentag, anzahl.
    """
    sql = f"""
        with days as (
            select distinct wochentag_nr, wochentag
            from lake.gold.dim_date
            where date_key <> -1
        ),
        counts as (
            select d.wochentag_nr, count(*) as anzahl
            from lake.gold.fct_drucksachen as f
            join lake.gold.dim_date as d using (date_key)
            where {_where()}
            group by all
        )
        select wochentag_nr, wochentag, coalesce(anzahl, 0) as anzahl
        from days
        left join counts using (wochentag_nr)
        order by wochentag_nr
    """
    return _df(con, sql, filters.params())


def vorgaenge_je_typ(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    """Procedures per type with how many are finished and how long promulgated ones took.

    Filtered by Wahlperiode only: a procedure spans many days, and its start is unknown for most
    of them until Bronze holds their full history, so a date filter would silently drop them.
    ``median_dauer_tage`` is a lower bound (see fct_vorgaenge) and NULL when no procedure of
    that type has been promulgated. Columns: vorgangstyp, anzahl, abgeschlossen, verkuendet,
    median_dauer_tage.
    """
    sql = f"""
        select
            f.vorgangstyp,
            count(*) as anzahl,
            count(*) filter (where f.is_abgeschlossen) as abgeschlossen,
            count(*) filter (where f.is_verkuendet) as verkuendet,
            median(f.dauer_tage) as median_dauer_tage
        from lake.gold.fct_vorgaenge as f
        where {_where(None)}
        group by all
        order by anzahl desc, vorgangstyp
    """
    return _df(con, sql, filters.params())

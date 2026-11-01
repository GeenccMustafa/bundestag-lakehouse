"""The dashboard's SQL against a tiny, hand-made Gold layer in a local DuckLake."""

from datetime import date
from pathlib import Path

import duckdb
import pytest

from dashboard import queries as q
from dashboard.lake import LakeConfigError, connect

# Two Fraktionen, one ministry, one known person; '-1' rows are the unknown members.
GOLD = """
create schema lake.gold;

create table lake.gold.dim_date as
select
    cast(strftime(d, '%Y%m%d') as integer) as date_key,
    cast(d as date) as datum,
    isodow(d) as wochentag_nr,
    ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'][
        isodow(d)
    ] as wochentag
from generate_series(timestamp '2025-01-01', timestamp '2026-12-31', interval 1 day) as t(d)
union all select -1, null, null, 'Unbekannt';

create table lake.gold.dim_fraktion (fraktion_key varchar, fraktion_name varchar);
insert into lake.gold.dim_fraktion values ('f_spd', 'SPD'),
    ('f_gruene', 'BÜNDNIS 90/DIE GRÜNEN'), ('-1', 'Unbekannt');

create table lake.gold.dim_ressort (ressort_key varchar, ressort_name varchar);
insert into lake.gold.dim_ressort values ('r_bmi', 'Bundesministerium des Innern'),
    ('-1', 'Unbekannt');

create table lake.gold.dim_person (person_key varchar, person_id varchar);
insert into lake.gold.dim_person values ('p1', '1'), ('p2', '2'), ('-1', null);

create table lake.gold.fct_aktivitaeten (
    aktivitaet_id varchar, date_key integer, person_key varchar, fraktion_key varchar,
    aktivitaetsart varchar, wahlperiode integer, aktualisiert_at timestamptz
);
insert into lake.gold.fct_aktivitaeten values
    ('a1', 20261005, 'p1', 'f_spd', 'Rede', 21, '2026-10-05 10:00+00'),
    ('a2', 20261005, 'p2', 'f_gruene', 'Rede', 21, '2026-10-05 11:00+00'),
    ('a3', 20261007, 'p2', 'f_gruene', 'Frage', 21, '2026-10-07 09:00+00'),
    ('a4', 20261007, '-1', '-1', 'Antwort', 21, '2026-10-07 09:00+00'),
    ('a5', 20250310, 'p1', 'f_spd', 'Rede', 20, '2025-03-10 09:00+00');

create table lake.gold.fct_drucksachen (
    drucksache_id varchar, date_key integer, ressort_key varchar, wahlperiode integer,
    aktualisiert_at timestamptz
);
-- 2026-10-05 is a Monday, 2026-10-07 a Wednesday.
insert into lake.gold.fct_drucksachen values
    ('d1', 20261005, 'r_bmi', 21, '2026-10-05 12:00+00'),
    ('d2', 20261007, '-1', 21, '2026-10-08 08:00+00');

create table lake.gold.fct_vorgaenge (
    vorgang_id varchar, vorgangstyp varchar, start_date_key integer, wahlperiode integer,
    is_abgeschlossen boolean, is_verkuendet boolean, dauer_tage integer,
    aktualisiert_at timestamptz
);
insert into lake.gold.fct_vorgaenge values
    ('v1', 'Gesetzgebung', 20261001, 21, true, true, 30, '2026-10-02 00:00+00'),
    ('v2', 'Gesetzgebung', -1, 21, false, false, null, '2026-10-02 00:00+00'),
    ('v3', 'Kleine Anfrage', -1, 20, true, false, null, '2025-01-02 00:00+00');
"""

OCTOBER = q.Filters(start=date(2026, 10, 1), end=date(2026, 10, 31))


def _make_lake(directory: Path) -> None:
    con = duckdb.connect()
    con.execute(
        f"ATTACH 'ducklake:{directory}/catalog.ducklake' AS lake (DATA_PATH '{directory}/data/')"
    )
    con.execute(GOLD)
    con.close()


@pytest.fixture(scope="module")
def lake_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("lake")
    _make_lake(directory)
    return directory


@pytest.fixture
def con(lake_dir: Path, monkeypatch: pytest.MonkeyPatch) -> duckdb.DuckDBPyConnection:
    monkeypatch.setenv("DBT_CI_DIR", str(lake_dir))
    return connect("ci")


def test_filters_bind_date_keys_and_wahlperiode() -> None:
    assert q.Filters(date(2026, 1, 2), date(2026, 12, 31), 21).params() == [20260102, 20261231, 21]


def test_ci_lake_is_read_only(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(duckdb.Error, match=r"read-only|read only"):
        con.execute("delete from lake.gold.fct_drucksachen")


def test_kpis_respect_range_and_count_only_known_persons(con: duckdb.DuckDBPyConnection) -> None:
    assert q.kpis(con, OCTOBER) == {
        "drucksachen": 2,
        "vorgaenge": 3,  # Wahlperiode filter only
        "aktivitaeten": 4,
        "personen": 2,
    }


def test_kpis_filter_by_wahlperiode(con: duckdb.DuckDBPyConnection) -> None:
    whole = q.Filters(date(2025, 1, 1), date(2026, 12, 31), wahlperiode=20)
    assert q.kpis(con, whole) == {
        "drucksachen": 0,
        "vorgaenge": 1,
        "aktivitaeten": 1,
        "personen": 1,
    }


def test_rankings_leave_out_unknown_members(con: duckdb.DuckDBPyConnection) -> None:
    fraktionen = q.aktivitaeten_je_fraktion(con, OCTOBER)
    assert fraktionen.to_dict("records") == [
        {"fraktion": "BÜNDNIS 90/DIE GRÜNEN", "anzahl": 2, "personen": 1},
        {"fraktion": "SPD", "anzahl": 1, "personen": 1},
    ]
    ressorts = q.drucksachen_je_ressort(con, OCTOBER)
    assert ressorts.to_dict("records") == [{"ressort": "Bundesministerium des Innern", "anzahl": 1}]


def test_aktivitaeten_je_art_counts_all_activities(con: duckdb.DuckDBPyConnection) -> None:
    arten = q.aktivitaeten_je_art(con, OCTOBER)
    assert dict(zip(arten.aktivitaetsart, arten.anzahl, strict=True)) == {
        "Rede": 2,
        "Frage": 1,
        "Antwort": 1,
    }


def test_timeline_fills_empty_days_with_zero(con: duckdb.DuckDBPyConnection) -> None:
    df = q.aktivitaeten_im_zeitverlauf(con, OCTOBER)
    assert [d.isoformat() for d in df.periode.dt.date] == ["2026-10-05", "2026-10-06", "2026-10-07"]
    assert df.anzahl.tolist() == [2, 0, 2]


@pytest.mark.parametrize(
    ("days", "grain"), [(0, "day"), (92, "day"), (93, "week"), (730, "week"), (731, "month")]
)
def test_zeit_grain_follows_range_length(days: int, grain: str) -> None:
    start = date(2024, 1, 1)
    end = date.fromordinal(start.toordinal() + days)
    assert q.zeit_grain(q.Filters(start, end)) == grain


def test_timeline_by_month(con: duckdb.DuckDBPyConnection) -> None:
    df = q.aktivitaeten_im_zeitverlauf(con, q.Filters(date(2024, 1, 1), date(2026, 12, 31)))
    assert len(df) == 20  # March 2025 .. October 2026, empty months included
    assert df.anzahl.sum() == 5


def test_wochentage_are_complete_and_ordered(con: duckdb.DuckDBPyConnection) -> None:
    df = q.drucksachen_je_wochentag(con, OCTOBER)
    assert df.wochentag.tolist()[0] == "Montag"
    assert len(df) == 7
    assert dict(zip(df.wochentag, df.anzahl, strict=True))["Mittwoch"] == 1


def test_vorgaenge_ignore_the_date_range(con: duckdb.DuckDBPyConnection) -> None:
    df = q.vorgaenge_je_typ(con, q.Filters(date(2026, 1, 1), date(2026, 1, 2), wahlperiode=21))
    assert df.to_dict("records") == [
        {
            "vorgangstyp": "Gesetzgebung",
            "anzahl": 2,
            "abgeschlossen": 1,
            "verkuendet": 1,
            "median_dauer_tage": 30.0,
        }
    ]


def test_date_bounds_and_wahlperioden(con: duckdb.DuckDBPyConnection) -> None:
    assert q.date_bounds(con) == (date(2025, 3, 10), date(2026, 10, 7))
    assert q.date_bounds(con, 20) == (date(2025, 3, 10), date(2025, 3, 10))
    assert q.wahlperioden(con) == [21, 20]


def test_freshness_reports_latest_snapshot_and_source_update(
    con: duckdb.DuckDBPyConnection,
) -> None:
    fresh = q.freshness(con)
    assert fresh["snapshot_id"] > 0
    assert fresh["source_updated_at"].date() == date(2026, 10, 8)


def test_connect_rejects_unknown_target() -> None:
    with pytest.raises(LakeConfigError, match="LAKE_TARGET"):
        connect("prod")


def test_connect_dev_needs_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("S3_ACCESS_KEY", "RUSTFS_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(LakeConfigError, match="RUSTFS_ACCESS_KEY"):
        connect("dev")

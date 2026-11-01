"""Streamlit dashboard on the Gold star schema.

    uv run --env-file .env streamlit run dashboard/app.py                 # real lake
    LAKE_TARGET=ci uv run --env-file .env streamlit run dashboard/app.py  # sample-data lake

Read-only: it attaches the DuckLake catalog READ_ONLY and only ever runs SELECTs (see
dashboard/lake.py). Results are cached for ten minutes, so moving the filters back and forth
does not hit Postgres and RustFS again.
"""

import sys
from datetime import timedelta
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

# `streamlit run` puts only this file's folder on sys.path; the package lives one level up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard import queries
from dashboard.lake import LakeConfigError, connect

ACCENT = "#2a78d6"  # categorical slot 1 of the dataviz reference palette; one series per chart
CACHE_TTL = 600

st.set_page_config(page_title="Bundestag Lakehouse", page_icon="🏛️", layout="wide")


@st.cache_resource(show_spinner=False)
def _connection() -> duckdb.DuckDBPyConnection:
    return connect()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _run(name: str, *args):
    # One cursor per call: Streamlit serves each viewer from its own thread, and a DuckDB
    # connection must not be shared across threads.
    return getattr(queries, name)(_connection().cursor(), *args)


def _kurz(ressort: str) -> str:
    """Shorten "Bundesministerium für X" to "BM für X": the truncated axis label keeps X."""
    return ressort.replace("Bundesministerium", "BM", 1)


def _bar(df: pd.DataFrame, category: str, value: str, title: str):
    """Horizontal bar chart, one series, largest on top, every column in the tooltip."""
    return (
        alt.Chart(df)
        .mark_bar(color=ACCENT, cornerRadiusEnd=4, height={"band": 0.7})
        .encode(
            x=alt.X(f"{value}:Q", title=title, axis=alt.Axis(tickMinStep=1)),
            y=alt.Y(f"{category}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=170)),
            tooltip=[alt.Tooltip(f"{c}:{'Q' if df[c].dtype.kind in 'iuf' else 'N'}") for c in df],
        )
    )


# Per time grain: Vega-Lite time unit (one band per bucket, so bars have width), axis label
# and tooltip format, and the panel title.
_GRAIN = {
    "day": ("yearmonthdate", "%d.%m.", "%d.%m.%Y", "Aktivitäten pro Tag"),
    "week": ("yearweek", "KW %V", "Woche ab %d.%m.%Y", "Aktivitäten pro Woche"),
    "month": ("yearmonth", "%m.%Y", "%B %Y", "Aktivitäten pro Monat"),
}


def _timeline(df: pd.DataFrame, grain: str):
    """Vertical bars over time, one per bucket of `grain`."""
    unit, axis_format, tooltip_format, _ = _GRAIN[grain]
    return (
        alt.Chart(df)
        .mark_bar(color=ACCENT, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                f"{unit}(periode):T",
                title=None,
                axis=alt.Axis(format=axis_format, labelOverlap="greedy", tickMinStep=1),
            ),
            y=alt.Y("anzahl:Q", title="Anzahl", axis=alt.Axis(tickMinStep=1)),
            tooltip=[
                alt.Tooltip("periode:T", title="Zeitraum", format=tooltip_format),
                alt.Tooltip("anzahl:Q", title="Anzahl"),
            ],
        )
    )


def _columns(df: pd.DataFrame, x: str, value: str):
    """Vertical bars over a nominal axis, in the data's own order (e.g. Monday first)."""
    return (
        alt.Chart(df)
        .mark_bar(color=ACCENT, cornerRadiusEnd=4)
        .encode(
            x=alt.X(f"{x}:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{value}:Q", title="Anzahl", axis=alt.Axis(tickMinStep=1)),
            tooltip=[alt.Tooltip(f"{x}:N"), alt.Tooltip(f"{value}:Q", title="Anzahl")],
        )
    )


def _panel(title: str, caption: str, chart, df: pd.DataFrame) -> None:
    """A chart with its question, an empty state and the numbers as a table."""
    st.subheader(title)
    st.caption(caption)
    if df.empty or ("anzahl" in df and df["anzahl"].sum() == 0):
        st.info("Keine Daten für diese Auswahl.")
        return
    st.altair_chart(chart, width="stretch")
    with st.expander("Tabelle"):
        st.dataframe(df, hide_index=True, width="stretch")


def _sidebar() -> queries.Filters:
    st.sidebar.header("Filter")
    periods = _run("wahlperioden")
    wp = st.sidebar.selectbox(
        "Wahlperiode", [None, *periods], format_func=lambda v: "Alle" if v is None else f"{v}."
    )
    first, last = _run("date_bounds", wp)
    # Default: a whole term when one is chosen, else the last 90 days with data. A few facts are
    # decades old (late updates of old papers), and the full range would squeeze the recent
    # activity into one bar.
    default_start = first if wp else max(first, last - timedelta(days=89))
    picked = st.sidebar.date_input(
        "Zeitraum",
        value=(default_start, last),
        min_value=first,
        max_value=last,
        format="DD.MM.YYYY",
        # A new key per Wahlperiode resets the picker to that term's range.
        key=f"zeitraum-{wp}",
    )
    # While the user is choosing, date_input returns only the start date.
    start, end = (picked[0], picked[-1]) if isinstance(picked, tuple) else (picked, picked)

    fresh = _run("freshness")
    st.sidebar.header("Datenstand")
    st.sidebar.markdown(
        f"- DIP zuletzt aktualisiert: **{fresh['source_updated_at']:%d.%m.%Y %H:%M}**\n"
        f"- Letzter dbt-Lauf: **{fresh['snapshot_time']:%d.%m.%Y %H:%M}**\n"
        f"- DuckLake-Snapshot: **#{fresh['snapshot_id']}**"
    )
    st.sidebar.caption(
        "Daten: [DIP-API des Deutschen Bundestages](https://dip.bundestag.de/). "
        "Vorgänge werden nur nach Wahlperiode gefiltert."
    )
    return queries.Filters(start=start, end=end, wahlperiode=wp)


def main() -> None:
    """Render the page: filters, headline numbers, then one panel per question."""
    st.title("Bundestag Lakehouse")
    st.caption("Gold-Schicht (Sternschema) aus der DIP-API: Drucksachen, Vorgänge, Aktivitäten.")

    try:
        filters = _sidebar()
    except (LakeConfigError, duckdb.Error) as exc:
        st.error(
            "Der Lake ist nicht erreichbar. Läuft `docker compose up -d postgres rustfs`, und "
            "wurde mit `uv run --env-file .env` gestartet?"
        )
        st.exception(exc)
        st.stop()

    k = _run("kpis", filters)
    cols = st.columns(4)
    cols[0].metric("Drucksachen", f"{k['drucksachen']:,}".replace(",", "."))
    cols[1].metric("Vorgänge", f"{k['vorgaenge']:,}".replace(",", "."))
    cols[2].metric("Aktivitäten", f"{k['aktivitaeten']:,}".replace(",", "."))
    cols[3].metric("Aktive Personen", f"{k['personen']:,}".replace(",", "."))

    left, right = st.columns(2)
    with left:
        df = _run("aktivitaeten_je_fraktion", filters)
        _panel(
            "Aktivitäten je Fraktion",
            "Fraktion zum Zeitpunkt der Aktivität (aus dem DIP-Titel), ohne Nicht-Abgeordnete.",
            _bar(df, "fraktion", "anzahl", "Aktivitäten"),
            df,
        )
    with right:
        df = _run("drucksachen_je_ressort", filters)
        _panel(
            "Drucksachen je Ressort",
            "Federführendes Ministerium; Drucksachen ohne Ressort sind nicht enthalten.",
            _bar(df.assign(kurz=df["ressort"].map(_kurz)), "kurz", "anzahl", "Drucksachen"),
            df,
        )

    left, right = st.columns(2)
    with left:
        grain = queries.zeit_grain(filters)
        df = _run("aktivitaeten_im_zeitverlauf", filters)
        _panel(
            _GRAIN[grain][3],
            "Zeiträume ohne Aktivität zählen als 0. Die Einteilung folgt der Länge des Zeitraums.",
            _timeline(df, grain),
            df,
        )
    with right:
        df = _run("drucksachen_je_wochentag", filters)
        _panel(
            "Drucksachen je Wochentag",
            "An welchen Tagen erscheinen Drucksachen?",
            _columns(df, "wochentag", "anzahl"),
            df,
        )

    left, right = st.columns(2)
    with left:
        df = _run("aktivitaeten_je_art", filters)
        _panel(
            "Aktivitäten je Art",
            "Rede, Anfrage, Antrag ...",
            _bar(df, "aktivitaetsart", "anzahl", "Aktivitäten"),
            df,
        )
    with right:
        st.subheader("Vorgänge je Typ")
        st.caption(
            "Dauer = Tage vom ersten bekannten Schritt bis zur Verkündung (Untergrenze, solange "
            "Bronze nicht die ganze Historie enthält)."
        )
        df = _run("vorgaenge_je_typ", filters)
        st.dataframe(
            df,
            hide_index=True,
            width="stretch",
            column_config={
                "vorgangstyp": "Typ",
                "anzahl": "Anzahl",
                "abgeschlossen": "Abgeschlossen",
                "verkuendet": "Verkündet",
                "median_dauer_tage": st.column_config.NumberColumn("Median Dauer (Tage)"),
            },
        )


main()

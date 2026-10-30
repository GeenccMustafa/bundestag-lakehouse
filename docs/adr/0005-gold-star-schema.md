# 0005. Gold layer: star schema, SCD2 persons, point-in-time Fraktion
Date: 2026-10-30 · Status: accepted

## Context
Silver holds one clean table per DIP entity. Analysts need to ask questions across entities —
"which ministry produces the most papers", "how active is each Fraktion", "how long does a law
take" — without re-deriving joins and business rules each time. Two complications:

- A person's Fraktion and role change over time; an activity must be attributed to the Fraktion
  the person belonged to *on that day*.
- The DIP `person` entity is sparsely loaded (Bronze has recent changes only, and since
  2026-10-25 the DIP domain redirects all non-browser clients to a bot challenge, so a full load
  is not possible). 569 persons appear in activities, 2 in the person entity.

## Decision
- **Kimball star schema** in DuckLake schema `gold`, all models documented with their grain:
  `fct_drucksachen` (per Drucksache), `fct_vorgaenge` (per Vorgang), `fct_aktivitaeten` (per
  Aktivität); conformed dimensions `dim_date`, `dim_person`, `dim_fraktion`, `dim_ressort`.
- **Unknown members** (`'-1'`, date_key `-1`) in every dimension, so fact keys are never NULL and
  fact→dimension relationship tests are errors.
- **`dim_person` is SCD Type 2** via the dbt snapshot `snp_person` (check strategy on name, role,
  current Fraktion). The snapshot can only record history from its first run, so each person's
  first version is back-dated to 1900-01-01.
- **Fraktion on facts is point-in-time from the source**: DIP prints the actor of every activity as
  "Name, MdB, Fraktion" at the time of the activity; `int_aktivitaet__akteur` parses it. This is
  more accurate than looking up a current Fraktion and works without the person entity.
- `int_person` fills person names from activities when the person entity is missing.
- **`fct_aktivitaeten` is incremental** (`delete+insert` on `aktivitaet_id`, 3-day lookback on
  `aktualisiert_at`); verified to equal a `--full-refresh`. The other Gold tables are small and
  rebuilt with `ducklake_table`.
- Reusable questions live in `dbt/analyses/` and compile against the current Gold tables.

## Alternatives considered
- **One wide table per question** — quick, but every question re-implements joins and
  attribution rules; no shared dimensions.
- **Fraktion only via SCD2 person dimension** — correct only from the snapshot's first run on and
  only for persons in the person entity; would attribute most activities to "unknown".
- **Derive person history from `person_roles` per Wahlperiode** — exact for past terms, but role
  changes inside a term (e.g. becoming a minister) are invisible; kept as Silver data, may feed a
  bridge table later.
- **`merge` for the incremental fact** — supported by dbt-duckdb on DuckLake, but `delete+insert`
  is simpler and equivalent for a single unique key.

## Consequences
- Gold answers the target questions today; numbers grow as Bronze grows, with no model changes.
- `fct_vorgaenge.dauer_tage` uses the first step we hold, so it is a lower bound until Bronze
  covers each procedure's full history.
- Activity titles are a parsing contract: if DIP changes their format, `int_aktivitaet__akteur`'s
  unit test and the `akteur_rolle` not-null test will catch it.
- `dbt build` must run the snapshot regularly (Phase 4 orchestrates it) or person history has gaps.

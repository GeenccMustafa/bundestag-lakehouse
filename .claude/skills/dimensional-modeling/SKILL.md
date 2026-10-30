---
name: dimensional-modeling
description: Kimball-style dimensional modeling rules for the Gold layer — grain, facts vs dimensions, surrogate keys, conformed dimensions, date dimension, and SCD Type 2 with dbt snapshots. Use when designing or reviewing fct_/dim_ models, snapshots, incremental marts, or when answering "what is the grain of this table?" or "should this be a fact or a dimension?".
---

# Dimensional Modeling (Gold layer)

## The four-step design process (Kimball)

Do these in order for every new fact table, and write the answers in the model's YAML `description`:

1. **Business process** — e.g. "a Drucksache is published", "a Vorgang moves through the legislative process".
2. **Grain** — one sentence: "one row per Drucksache", "one row per Vorgang". If you can't state it in one sentence, the model isn't ready.
3. **Dimensions** — the who/what/when/where that describe each row at that grain (person, Fraktion, Ressort, date).
4. **Facts** — the numeric measurements true at that grain (counts, durations in days).

## Rules

- **Grain is enforced by a test**: a `unique` test (or `dbt_utils.unique_combination_of_columns`) on the grain columns of every fact.
- **Facts** hold foreign keys + measures + degenerate dimensions (e.g. `drucksache_nummer`). No descriptive text that belongs in a dimension.
- **Dimensions** are wide and descriptive, one row per member (or per version for SCD2). Every dimension has an "unknown" member (key `-1` or a hashed `'unknown'`), so facts never have null FKs.
- **Surrogate keys** via `dbt_utils.generate_surrogate_key([...])` over the natural key (+ `valid_from` for SCD2). Natural keys stay as columns too.
- **Conformed dimensions**: `dim_date`, `dim_person`, `dim_fraktion` are shared by all facts; never build a fact-specific copy.
- **`relationships` tests** from every fact FK to its dimension.
- Additive measures where possible; document semi-/non-additive ones (e.g. durations are averageable, not summable across time).

## SCD Type 2 with dbt snapshots

Use for attributes whose history matters — e.g. a person's Fraktion or role changes.

- Put snapshots in `snapshots/` named `snp_<entity>`, sourcing from the **staging** model.
- Prefer `strategy: timestamp` with `updated_at: aktualisiert` (DIP provides it); fall back to `check` on specific columns only if there is no trustworthy timestamp.
- The dimension built on the snapshot exposes `valid_from`, `valid_to`, `is_current`. Facts join with `fact_date between valid_from and coalesce(valid_to, '9999-12-31')` so each fact sees the version that was true at the time.
- Test: at most one `is_current = true` row per natural key; no overlapping validity windows.

## Incremental fact models

- `materialized='incremental'` with `unique_key` = the grain, and `incremental_strategy` `merge` or `delete+insert` (pick per adapter; record the choice in an ADR).
- Filter with `{% if is_incremental() %} where aktualisiert > (select max(aktualisiert) from {{ this }}) {% endif %}` — consider a lookback window for late-arriving updates.
- Always make sure `--full-refresh` produces the same result as the incremental history. Add a CI check or a periodic job that compares them if drift is suspected.

## Models in this project (ADR 0005)

| Model | Grain | Notes |
|-------|-------|-------|
| `fct_drucksachen` | one row per Drucksache | lead Ressort, primary originator type (`int_drucksache__urheber`), Fraktion |
| `fct_vorgaenge` | one row per Vorgang | first known step, Verkündung, `dauer_tage` (lower bound) |
| `fct_aktivitaeten` | one row per Aktivität | incremental delete+insert; SCD2 person as of date; Fraktion parsed from the activity title |
| `dim_person` | one row per person version | from snapshot `snp_person`; first version back-dated to 1900-01-01 |
| `dim_fraktion` | one row per Fraktion | DIP spelling; originators normalised with `fraktion_from_urheber` |
| `dim_ressort` | one row per ministry | |
| `dim_date` | one row per day | generated spine + `wahlperioden` seed |

Every dimension has an unknown member (`'-1'` / date_key `-1`); use the `unknown_key()` and
`date_key()` macros instead of literals. SCD2 integrity is tested with the generic test
`scd2_valid_ranges`.

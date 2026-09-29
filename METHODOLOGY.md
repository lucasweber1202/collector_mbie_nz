# MBIE weekly fuel prices — methodology

Authority: `guimasuko/collector_template` main `4bc65765cedd9c14aec196cff382df6dfb318c77`;
`NZD` is in its `metadata.country` vocabulary and is what this collector emits.

## Source

Official weekly table
`https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv`
from MBIE's [weekly fuel price monitoring](https://www.mbie.govt.nz/building-and-energy/energy-and-natural-resources/energy-statistics-and-modelling/energy-statistics/weekly-fuel-price-monitoring).
The page describes a method change from 27 February 2026 to importer
cost/margin series. On 2026-09-27 the CSV had 35,100 rows, 23 April 2004 to
18 September 2026.

## Unattended acquisition (resolved)

mbie.govt.nz sits behind Imperva (Incapsula). Measured on 2026-09-27 from this
session:

| Client | CSV | Landing page |
| --- | --- | --- |
| Python `httpx` claiming to be Chrome (the previous default User-Agent) | 0/4 — HTTP **200** `text/html` Incapsula challenge | challenge |
| Python `httpx`, honest `collector_mbie_nz/1.0 (+repo URL)` User-Agent | 5/5 — `application/octet-stream`, 2,888,957 bytes | challenge |
| Python `httpx` default `python-httpx` User-Agent | 5/5 | challenge |

The earlier "terminal HTTP received an Incapsula challenge" was caused by the
collector impersonating a browser from a non-browser TLS stack. The collector
now identifies itself honestly (`scripts/config.py`). There is no cookie, token
replay, JavaScript execution or other anti-bot evasion. The HTML landing page
stays a JavaScript challenge for any non-browser client, so it is not read.

A challenge can never be parsed as data: `check_payload` refuses a body with
`Content-Type: text/html`, an HTML start or Incapsula/captcha markers (note the
challenge arrives with status 200), a body that does not start with the audited
`"Week","Date","Fuel","Variable","Value","Unit","Status"` header, and a file
under 1 MB. `parse_csv` then requires 30,000 source rows, exactly the 12
selected series, at least 1,000 weeks each, unique `(series_id, week)` keys,
known units and numeric values; failures raise `SourceAccessError` or
`SourceLayoutError` before any write.

## Series

For diesel, regular petrol and premium 95R: adjusted retail price, board price
and importer cost (NZD c/L). Also Dubai crude (USD/bbl and NZD/bbl) and the
USD/NZD exchange rate. 12 IDs, 14,040 observations, 1,170 weeks each. Exact
source units live in names/descriptions; canonical `unit` is `other` for
prices and `ratio` for FX. `Final` and `Provisional` are accepted. Tax
components, ETS and importer margin are excluded as redundant or derived.

## Release monitoring

MBIE's publication note is only on the challenged landing page and the CSV
has no `Last-Modified`/`ETag`, so no official publication date is claimed.
Under Masuko sections 3 and 13.7, mandatory `metadata.last_publish_date` is
`DATE(MAX(time_series.collected_at))` per series. This is a collection-derived
fallback, not evidence of an official MBIE release. An unchanged rerun retains
the stored date and timestamp. The release evidence is the latest week the
file covers: a later week is `new_release`; the same week with changed values
(e.g. `Provisional` → `Final`) is `revised_source`; otherwise `same_release`.
`layout_changed` is logged on `SourceLayoutError`.

## Date semantics

- `reference_date`: the weekly period reported by MBIE.
- `last_publish_date`: official release date when trustworthy; for this CSV,
  the per-series collection-derived fallback required by Masuko.
- `collected_at`: the timestamp at which this pipeline stored a changed value.
- `vintage_date`: the UTC collection day; an unchanged rerun creates no vintage.

## Point in time

The CSV is a revised current archive, not historical snapshots; MBIE's 2026
method change is material for PIT research. `vintage_date` is the UTC
collection date, so the first backfill is dated the day it was collected.
Later changes become new vintages; same-day changes overwrite that day's
vintage (template rule).

## Verification (2026-09-27)

- PostgreSQL 16.13, live unattended `main.py`: run 1 wrote 14,040 observations
  and 12 metadata rows (`first_release`); run 2 wrote nothing (`same_release`).
- `tests/test_postgres_integration.py`: canonical tables, idempotent rerun,
  later-day vintage, same-day overwrite, metadata MERGE with NULL in every
  nullable column (`description`, `frequency`, `unit`, `first_observation`,
  `last_observation`); `eco_group` and `last_publish_date` are mandatory, time-series MERGE, run log, release classification.
- All emitted SQL parses with the Spark SQL grammar (pyspark 4.1.1).
  **Databricks corporate runtime: not verified.**

## Masuko authority verification

Pinned authority: `guimasuko/collector_template@4bc65765cedd9c14aec196cff382df6dfb318c77`. Physical `.github/` and `.vscode/` paths are checked against Git blobs. `.gitignore` and `scripts/databricks_engine.py` have no physical path in the template tree; they are canonical fenced blocks in `GUIDELINES.md` sections 8.1 and 8.9. The guideline Git blob is `089fbbca6a2241d3f02777b82631fbf81d49f6e0`; the two derived file blobs are `f0d1368264d24d7959d3137d618930a06f33795e` and `73821f7a530ab5cca2f5313180d71c17173e6e59`. `tests/test_architecture.py` checks all local blobs on every run. For independent source derivation, check out the exact authority commit and run `MASUKO_TEMPLATE_DIR=/path/to/collector_template python -m pytest -q tests/test_architecture.py`. This checks the guideline blob, extracts both fenced blocks and checks their hashes.

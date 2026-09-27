# MBIE weekly fuel prices — methodology

Authority: `guimasuko/collector_template` main `723f8633bbd367ad9cca0a199e84b10fd355da36`;
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
has no `Last-Modified`/`ETag`, so no publication date is claimed
(`last_publish_date` stays NULL). The release evidence is the latest week the
file covers: a later week is `new_release`; the same week with changed values
(e.g. `Provisional` → `Final`) is `revised_source`; otherwise `same_release`.
`layout_changed` is logged on `SourceLayoutError`.

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
  nullable column (including `last_publish_date`, which is NULL here in
  production), time-series MERGE, run log, release classification.
- All emitted SQL parses with the Spark SQL grammar (pyspark 4.1.1).
  **Databricks corporate runtime: not verified.**

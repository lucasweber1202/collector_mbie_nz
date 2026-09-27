# MBIE weekly fuel price predictors

Standalone Python 3.11 collector of MBIE's official weekly fuel price
monitoring CSV: adjusted retail, board price and importer cost for three fuels,
Dubai crude and USD/NZD (12 series, weekly from 2004). Fetched unattended with
an honest User-Agent; bot-protection pages are refused, never parsed.
Canonical `metadata`, `time_series` and `logs` with vintages.

Set `COLLECTOR_DB_URL=postgresql+psycopg2://...` or `PROD=true` for Databricks.
Tests: `pytest` (Spark grammar needs `java`); `COLLECTOR_TEST_PG_URL` for the
PostgreSQL write paths, `MBIE_LIVE_SMOKE=1` for the live fetch. See
METHODOLOGY.md.

# MBIE weekly fuel predictor collector (draft)

Standalone Python 3.11 collector for the official [MBIE weekly fuel table](https://www.mbie.govt.nz/building-and-energy/energy-and-natural-resources/energy-statistics-and-modelling/energy-statistics/weekly-fuel-price-monitoring). Twelve curated fuel-price, importer-cost, crude-price and exchange-rate series, stored in the canonical `metadata`, `time_series`, and `logs` tables with observation vintages.

`COLLECTOR_DB_URL=postgresql+psycopg2://... python main.py` runs locally; `PROD=true` uses the corporate Databricks configuration. The CSV host currently returns an anti-bot HTML challenge to terminal HTTP clients in this environment, so the default `collect()` fails loudly until source access is resolved. The official CSV was downloaded through the browser and its 35,100 rows parsed and verified locally. This PR is not production ready. See `METHODOLOGY.md`.

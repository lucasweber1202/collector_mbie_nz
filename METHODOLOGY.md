# MBIE weekly fuel source

Official weekly table: `https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv`. The 23 September 2026 page reports data through 18 September and describes a method change applied from 27 February 2026 to importer cost/margin series. The CSV downloaded via official browser link contained 35,100 rows, 2004-04-23 to 2026-09-18. Curated output has 12 IDs and 14,040 observations, each with 1,170 weeks.

The three fuel types each retain adjusted retail price, board price and importer cost. Dubai crude in USD/bbl and NZD/bbl plus USD/NZD are supporting predictors. Tax components, ETS, and importer margin trends are excluded as redundant or derived. Exact source units live in names/descriptions; canonical `unit` is `other` for fuel/crude prices and `ratio` for FX. `Final` and `Provisional` are accepted. The CSV is a revised current archive, not historical point-in-time snapshots. MBIE's 2026 adjustment is especially material for PIT research.

**Gate:** terminal HTTP access received an Incapsula HTML challenge. A normal collector run will reject it; parsing was tested against the actual CSV downloaded via the official page in a cloud browser, but a fully automated source fetch is not yet verified. PostgreSQL/idempotency, Databricks runtime and clean-room remain pending. NZD vocabulary awaits template PR #1.

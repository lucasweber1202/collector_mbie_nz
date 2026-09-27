"""Build small CSVs in the audited MBIE weekly-table layout."""

from __future__ import annotations

from datetime import date, timedelta

HEADER = b'"Week","Date","Fuel","Variable","Value","Unit","Status"\n'
SERIES = [
    (fuel, variable, "NZD c/L")
    for fuel in ("Diesel", "Regular Petrol", "Premium Petrol 95R")
    for variable in ("Adjusted retail price", "Board price", "Importer cost")
] + [("NA", "Dubai crude price", "USD/bbl"), ("NA", "Dubai crude price", "NZD/bbl"), ("NA", "Exchange rate", "USD/NZD")]


def weekly(weeks: int = 2, start: date = date(2026, 9, 11), extra: bytes = b"") -> bytes:
    lines = [HEADER]
    for n in range(weeks):
        day = start + timedelta(days=7 * n)
        week = f"{day.isocalendar().year}w{day.isocalendar().week:02d}"
        for i, (fuel, variable, unit) in enumerate(SERIES):
            value = 0.6 + n / 100 if unit == "USD/NZD" else 100 + i + n
            lines.append(f'"{week}",{day.isoformat()},"{fuel}","{variable}",{value},"{unit}","Provisional"\n'.encode())
        lines.append(f'"{week}",{day.isoformat()},"Diesel","Taxes",50,"NZD c/L","Final"\n'.encode())
    return b"".join(lines) + extra

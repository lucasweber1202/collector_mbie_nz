"""Parse the official MBIE weekly fuel price monitoring CSV."""
from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from scripts.config import REQUEST_TIMEOUT, USER_AGENT
from scripts.time_series import Observation

SOURCE_URL = "https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv"
PAGE_URL = "https://www.mbie.govt.nz/building-and-energy/energy-and-natural-resources/energy-statistics-and-modelling/energy-statistics/weekly-fuel-price-monitoring"
FIELDS = {"Week", "Date", "Fuel", "Variable", "Value", "Unit", "Status"}
FUEL_CODES = {"Diesel": "DIESEL", "Regular Petrol": "REGULAR", "Premium Petrol 95R": "PREMIUM95", "NA": "ALL"}
VARIABLES = {"Adjusted retail price": "ADJUSTED_RETAIL", "Board price": "BOARD",
             "Importer cost": "IMPORTER_COST", "Dubai crude price": "DUBAI_CRUDE",
             "Exchange rate": "EXCHANGE_RATE"}
SELECTED = {(fuel, variable) for fuel in ("Diesel", "Regular Petrol", "Premium Petrol 95R")
            for variable in ("Adjusted retail price", "Board price", "Importer cost")}
SELECTED |= {("NA", "Dubai crude price"), ("NA", "Exchange rate")}
UNITS = {"NZD c/L", "USD/bbl", "NZD/bbl", "USD/NZD"}


@dataclass(frozen=True)
class SourceData:
    observations: list[Observation]
    catalog: dict[str, dict[str, Any]]


def build_series_id(fuel: str, variable: str, unit: str) -> str:
    if (fuel, variable) not in SELECTED or unit not in UNITS:
        raise ValueError(f"Invalid MBIE series: {fuel}, {variable}, {unit}")
    if fuel != "NA" and unit != "NZD c/L":
        raise ValueError("Fuel component unit changed")
    if variable == "Exchange rate" and unit != "USD/NZD":
        raise ValueError("Exchange rate unit changed")
    if variable == "Dubai crude price" and unit not in {"USD/bbl", "NZD/bbl"}:
        raise ValueError("Crude unit changed")
    code = f"MBIE_{FUEL_CODES[fuel]}_{VARIABLES[variable]}_{unit.replace(' ', '_').replace('/', '_').upper()}"
    if not re.fullmatch(r"[A-Z0-9_]+", code):
        raise ValueError("Invalid MBIE ID")
    return code


def parse_csv(blob: bytes) -> SourceData:
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig")))
    if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
        raise ValueError("MBIE weekly CSV header changed or response is not CSV")
    snapshot = hashlib.sha256(blob).hexdigest()
    observations: list[Observation] = []
    catalog: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, date]] = set()
    for row in reader:
        key = row["Fuel"], row["Variable"]
        if key not in SELECTED:
            continue
        sid = build_series_id(*key, row["Unit"])
        ref = date.fromisoformat(row["Date"])
        if not re.fullmatch(r"\d{4}w\d{2}", row["Week"]) or row["Status"] not in {"Final", "Provisional"}:
            raise ValueError(f"Unexpected MBIE week/status: {row}")
        raw = row["Value"]
        if raw in ("", "NA"):
            continue
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError(f"Non-finite MBIE value: {sid} {ref}")
        descriptor = {"name": f"{row['Fuel']} {row['Variable']} ({row['Unit']})",
                      "description": f"MBIE weekly fuel monitoring; source unit {row['Unit']}",
                      "country": "NZD", "frequency": "weekly", "unit": "ratio" if row["Unit"] == "USD/NZD" else "other",
                      "eco_group": "exchange_rates" if row["Unit"] == "USD/NZD" else
                                   ("producer_prices" if row["Variable"] in ("Importer cost", "Dubai crude price") else "consumer_prices"),
                      "source_url": SOURCE_URL, "last_publish_date": None}
        if sid in catalog and catalog[sid] != descriptor:
            raise ValueError(f"Conflicting MBIE metadata: {sid}")
        catalog[sid] = descriptor
        economic_key = sid, ref
        if economic_key in seen:
            raise ValueError(f"Duplicate MBIE economic key: {economic_key}")
        seen.add(economic_key)
        observations.append(Observation(sid, ref, value, snapshot))
    if not observations:
        raise ValueError("No MBIE selected observations")
    return SourceData(observations, catalog)


def collect() -> SourceData:
    """Fetch the official CSV; fail loudly if its host challenges the runtime."""
    response = httpx.get(SOURCE_URL, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    response.raise_for_status()
    if not response.content.startswith((b'"Week"', b"Week,")):
        raise ValueError("MBIE returned a non-CSV response; check source access")
    return parse_csv(response.content)

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
from scripts.releases import ReleaseEvidence
from scripts.time_series import Observation

SOURCE_URL = "https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv"
PAGE_URL = "https://www.mbie.govt.nz/building-and-energy/energy-and-natural-resources/energy-statistics-and-modelling/energy-statistics/weekly-fuel-price-monitoring"
FIELDS = {"Week", "Date", "Fuel", "Variable", "Value", "Unit", "Status"}
FUEL_CODES = {
    "Diesel": "DIESEL",
    "Regular Petrol": "REGULAR",
    "Premium Petrol 95R": "PREMIUM95",
    "NA": "ALL",
}
VARIABLES = {
    "Adjusted retail price": "ADJUSTED_RETAIL",
    "Board price": "BOARD",
    "Importer cost": "IMPORTER_COST",
    "Dubai crude price": "DUBAI_CRUDE",
    "Exchange rate": "EXCHANGE_RATE",
}
SELECTED = {
    (fuel, variable)
    for fuel in ("Diesel", "Regular Petrol", "Premium Petrol 95R")
    for variable in ("Adjusted retail price", "Board price", "Importer cost")
}
SELECTED |= {("NA", "Dubai crude price"), ("NA", "Exchange rate")}
EXPECTED_SERIES = {(fuel, variable, "NZD c/L") for fuel, variable in SELECTED if fuel != "NA"} | {
    ("NA", "Dubai crude price", "USD/bbl"),
    ("NA", "Dubai crude price", "NZD/bbl"),
    ("NA", "Exchange rate", "USD/NZD"),
}
UNITS = {"NZD c/L", "USD/bbl", "NZD/bbl", "USD/NZD"}
CSV_MAGIC = b'"Week","Date","Fuel","Variable","Value","Unit","Status"'
MIN_PAYLOAD_BYTES = 1_000_000
MIN_SOURCE_ROWS = 30_000
MIN_WEEKS_PER_SERIES = 1_000
CHALLENGE_MARKERS = (
    b"_incapsula_resource",
    b"incapsula",
    b"captcha",
    b"cf-mitigated",
    b"just a moment",
    b"pardon our interruption",
    b"access denied",
)


class SourceLayoutError(ValueError):
    """The MBIE CSV no longer has the audited layout."""


class SourceAccessError(RuntimeError):
    """MBIE answered with a challenge or error page instead of the CSV."""


@dataclass(frozen=True)
class SourceData:
    observations: list[Observation]
    catalog: dict[str, dict[str, Any]]
    releases: tuple[ReleaseEvidence, ...] = ()


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


def check_payload(response: httpx.Response) -> bytes:
    """Refuse a challenge/HTML page, a changed header or a truncated file."""
    response.raise_for_status()
    blob = response.content
    lowered = blob[:4096].lower()
    content_type = response.headers.get("content-type", "").lower()
    if (
        "text/html" in content_type
        or lowered.lstrip().startswith((b"<html", b"<!doctype"))
        or any(m in lowered for m in CHALLENGE_MARKERS)
    ):
        raise SourceAccessError(
            f"MBIE served an HTML/bot-protection page instead of the CSV ({content_type or 'no content type'}); "
            "the collector must identify itself honestly (see COLLECTOR_USER_AGENT in scripts/config.py)"
        )
    if not blob.removeprefix(b"\xef\xbb\xbf").startswith(CSV_MAGIC):
        raise SourceLayoutError("MBIE weekly CSV does not start with the audited header")
    if len(blob) < MIN_PAYLOAD_BYTES:
        raise SourceAccessError(f"MBIE weekly CSV is implausibly small ({len(blob)} bytes)")
    return blob


def parse_csv(
    blob: bytes, min_rows: int = MIN_SOURCE_ROWS, min_weeks: int = MIN_WEEKS_PER_SERIES
) -> SourceData:
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig")))
    if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
        raise SourceLayoutError("MBIE weekly CSV header changed or response is not CSV")
    snapshot = hashlib.sha256(blob).hexdigest()
    observations: list[Observation] = []
    catalog: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, date]] = set()
    rows = 0
    for row in reader:
        rows += 1
        key = row["Fuel"], row["Variable"]
        if key not in SELECTED:
            continue
        sid = build_series_id(*key, row["Unit"])
        ref = date.fromisoformat(row["Date"])
        if not re.fullmatch(r"\d{4}w\d{2}", row["Week"]) or row["Status"] not in {
            "Final",
            "Provisional",
        }:
            raise ValueError(f"Unexpected MBIE week/status: {row}")
        raw = row["Value"]
        if raw in ("", "NA"):
            continue
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError(f"Non-numeric MBIE value {raw!r}: {sid} {ref}") from exc
        if not math.isfinite(value):
            raise ValueError(f"Non-finite MBIE value: {sid} {ref}")
        descriptor = {
            "name": f"{row['Fuel']} {row['Variable']} ({row['Unit']})",
            "description": f"MBIE weekly fuel monitoring; source unit {row['Unit']}",
            "country": "NZD",
            "frequency": "weekly",
            "unit": "ratio" if row["Unit"] == "USD/NZD" else "other",
            "eco_group": "exchange_rates"
            if row["Unit"] == "USD/NZD"
            else (
                "producer_prices"
                if row["Variable"] in ("Importer cost", "Dubai crude price")
                else "consumer_prices"
            ),
            "source_url": SOURCE_URL,
            "last_publish_date": None,
        }
        if sid in catalog and catalog[sid] != descriptor:
            raise ValueError(f"Conflicting MBIE metadata: {sid}")
        catalog[sid] = descriptor
        economic_key = sid, ref
        if economic_key in seen:
            raise ValueError(f"Duplicate MBIE economic key: {economic_key}")
        seen.add(economic_key)
        observations.append(Observation(sid, ref, value, snapshot))
    if rows < min_rows:
        raise SourceLayoutError(f"MBIE weekly CSV has {rows} rows; expected at least {min_rows}")
    if set(catalog) != {
        build_series_id(fuel, variable, unit) for fuel, variable, unit in EXPECTED_SERIES
    }:
        raise SourceLayoutError(f"MBIE selected series changed: {sorted(catalog)}")
    for sid in catalog:
        weeks = sum(o.series_id == sid for o in observations)
        if weeks < min_weeks:
            raise SourceLayoutError(f"MBIE {sid} has {weeks} weeks; expected at least {min_weeks}")
    return SourceData(observations, catalog)


def collect() -> SourceData:
    """Fetch the official CSV; fail loudly if its host challenges the runtime.

    The landing page (with the human-readable publication note) is always an
    Incapsula JavaScript challenge for a non-browser client, so the release
    evidence is the latest week the file covers; no publication date is
    claimed.
    """
    with httpx.Client(
        timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        response = client.get(SOURCE_URL)
    data = parse_csv(check_payload(response))
    latest = max(o.reference_date for o in data.observations)
    evidence = ReleaseEvidence(
        "weekly_table_csv", SOURCE_URL, None, latest, frozenset(data.catalog)
    )
    return SourceData(data.observations, data.catalog, (evidence,))

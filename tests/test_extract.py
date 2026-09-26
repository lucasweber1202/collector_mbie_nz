"""Exercise the official MBIE weekly CSV contract."""
from __future__ import annotations

import os
from datetime import date

import pytest

from scripts.extract import build_series_id, collect, parse_csv


def test_id_and_duplicate_guard() -> None:
    sid = build_series_id("Diesel", "Board price", "NZD c/L")
    assert sid == "MBIE_DIESEL_BOARD_NZD_C_L"
    header = b'"Week","Date","Fuel","Variable","Value","Unit","Status"\n'
    row = b'"2026w38",2026-09-18,"Diesel","Board price",320,"NZD c/L","Provisional"\n'
    assert parse_csv(header + row).observations[0].reference_date == date(2026, 9, 18)
    with pytest.raises(ValueError, match="Duplicate"):
        parse_csv(header + row + row)
    with pytest.raises(ValueError, match="header"):
        parse_csv(b"<html>Access denied</html>")


@pytest.mark.skipif(os.getenv("MBIE_LIVE_SMOKE") != "1", reason="opt-in official network")
def test_live_source() -> None:
    result = collect()
    assert len(result.catalog) == 12
    assert len(result.observations) >= 14040

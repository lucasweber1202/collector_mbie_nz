"""Exercise the official MBIE weekly CSV contract."""

from __future__ import annotations

import os
from datetime import date

import httpx
import pytest

from scripts import config, metadata
from scripts.extract import (
    SourceAccessError,
    SourceLayoutError,
    build_series_id,
    check_payload,
    collect,
    parse_csv,
)
from tests.mbie_csv import HEADER, weekly


def test_id_and_duplicate_guard() -> None:
    sid = build_series_id("Diesel", "Board price", "NZD c/L")
    assert sid == "MBIE_DIESEL_BOARD_NZD_C_L"
    data = parse_csv(weekly(), min_rows=1, min_weeks=1)
    assert len(data.catalog) == 12 and len(data.observations) == 24
    assert data.observations[0].reference_date == date(2026, 9, 11)
    metadata.validate_catalog(data.catalog)
    fx = data.catalog["MBIE_ALL_EXCHANGE_RATE_USD_NZD"]
    assert (fx["unit"], fx["eco_group"], fx["frequency"], fx["country"]) == (
        "ratio",
        "exchange_rates",
        "weekly",
        "NZD",
    )
    duplicate = weekly(weeks=1).splitlines(keepends=True)[1]
    with pytest.raises(ValueError, match="Duplicate"):
        parse_csv(weekly(weeks=1) + duplicate, min_rows=1, min_weeks=1)
    with pytest.raises(SourceLayoutError, match="header"):
        parse_csv(b"<html>Access denied</html>")


def test_missing_series_short_history_and_short_file_fail() -> None:
    body = b"".join(
        line for line in weekly().splitlines(keepends=True) if b"Exchange rate" not in line
    )
    with pytest.raises(SourceLayoutError, match="series changed"):
        parse_csv(body, min_rows=1, min_weeks=1)
    with pytest.raises(SourceLayoutError, match="weeks"):
        parse_csv(weekly(), min_rows=1, min_weeks=3)
    with pytest.raises(SourceLayoutError, match="rows"):
        parse_csv(weekly(), min_weeks=1)


def _response(body: bytes, content_type: str) -> httpx.Response:
    return httpx.Response(
        200,
        content=body,
        headers={"content-type": content_type},
        request=httpx.Request("GET", "https://www.mbie.govt.nz/x.csv"),
    )


def test_incapsula_challenge_is_refused_even_with_status_200() -> None:
    challenge = b'<html>\r\n<head>\r\n<META NAME="robots" CONTENT="noindex,nofollow">\r\n<script src="/_Incapsula_Resource?SWJIYLWA=x"></script>'
    with pytest.raises(SourceAccessError, match="bot-protection"):
        check_payload(_response(challenge, "text/html"))
    with pytest.raises(SourceAccessError, match="bot-protection"):
        check_payload(_response(challenge, "application/octet-stream"))
    with pytest.raises(SourceLayoutError, match="header"):
        check_payload(_response(b'"Week","Date","Fuel"\n' * 100000, "application/octet-stream"))
    with pytest.raises(SourceAccessError, match="small"):
        check_payload(_response(HEADER, "application/octet-stream"))


def test_default_user_agent_is_honest() -> None:
    assert config.USER_AGENT.startswith("collector_mbie_nz/") or os.getenv("COLLECTOR_USER_AGENT")
    assert "Mozilla" not in config.USER_AGENT or os.getenv("COLLECTOR_USER_AGENT")


@pytest.mark.skipif(os.getenv("MBIE_LIVE_SMOKE") != "1", reason="opt-in official network")
def test_live_source() -> None:
    result = collect()
    assert len(result.catalog) == 12
    assert len(result.observations) >= 14040
    assert min(o.reference_date for o in result.observations) == date(2004, 4, 23)
    evidence = result.releases[0]
    assert evidence.published is None and evidence.latest_reference is not None
    assert evidence.latest_reference >= date(2026, 9, 18)

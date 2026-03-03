"""Tests for adaptive clock palette helpers."""

from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from pypixoo.clock_palette import (
    BandDecision,
    GeoLocation,
    SunWindow,
    compute_real_sun_window,
    compute_seasonal_tz_window,
    resolve_effective_band,
    resolve_hemisphere,
    resolve_location,
    select_day_or_night_band,
)


def test_resolve_location_prefers_cli():
    loc = resolve_location(latitude=40.0, longitude=-73.0, env={}, now_epoch=123.0)
    assert loc is not None
    assert loc.source == "cli"
    assert loc.latitude == pytest.approx(40.0)
    assert loc.longitude == pytest.approx(-73.0)


def test_resolve_location_uses_env():
    loc = resolve_location(
        latitude=None,
        longitude=None,
        env={"PIXOO_LATITUDE": "41.1", "PIXOO_LONGITUDE": "-72.3"},
        now_epoch=123.0,
    )
    assert loc is not None
    assert loc.source == "env"
    assert loc.latitude == pytest.approx(41.1)
    assert loc.longitude == pytest.approx(-72.3)


def test_resolve_location_uses_cache_before_network(tmp_path):
    cache_path = tmp_path / "geo.json"
    cache_path.write_text(
        json.dumps(
            {
                "latitude": 10.5,
                "longitude": 20.5,
                "source": "ipapi",
                "fetched_at": 1_000.0,
            }
        )
    )
    loc = resolve_location(
        latitude=None,
        longitude=None,
        env={},
        now_epoch=1_500.0,
        cache_path=cache_path,
    )
    assert loc is not None
    assert loc.source == "cache"
    assert loc.latitude == pytest.approx(10.5)
    assert loc.longitude == pytest.approx(20.5)


def test_resolve_location_cache_expiry_uses_fetch(monkeypatch, tmp_path):
    cache_path = tmp_path / "geo.json"
    cache_path.write_text(
        json.dumps(
            {
                "latitude": 1.0,
                "longitude": 2.0,
                "source": "ipapi",
                "fetched_at": 0.0,
            }
        )
    )
    fetched = GeoLocation(latitude=33.3, longitude=-122.2, source="ipapi", fetched_at=2_000_000.0)
    monkeypatch.setattr("pypixoo.clock_palette.fetch_ip_geolocation_ipapi", lambda **kwargs: fetched)
    loc = resolve_location(
        latitude=None,
        longitude=None,
        env={},
        now_epoch=2_000_000.0,
        cache_path=cache_path,
    )
    assert loc is not None
    assert loc.source == "ipapi"
    payload = json.loads(cache_path.read_text())
    assert payload["latitude"] == pytest.approx(33.3)
    assert payload["longitude"] == pytest.approx(-122.2)


def test_resolve_hemisphere_override_and_inference():
    assert resolve_hemisphere("America/New_York", env_override="south") == "south"
    assert resolve_hemisphere("Australia/Sydney", env_override=None) == "south"
    assert resolve_hemisphere("America/New_York", env_override=None) == "north"


def test_compute_seasonal_tz_window_inverts_by_hemisphere():
    tz = ZoneInfo("UTC")
    local_dt = datetime(2026, 6, 21, 12, 0, tzinfo=tz)
    north = compute_seasonal_tz_window(local_dt, hemisphere="north")
    south = compute_seasonal_tz_window(local_dt, hemisphere="south")

    north_hours = (north.sunset - north.sunrise).total_seconds() / 3600.0
    south_hours = (south.sunset - south.sunrise).total_seconds() / 3600.0
    assert north_hours > south_hours


def test_select_day_or_night_band_boundaries():
    tz = ZoneInfo("UTC")
    sunrise = datetime(2026, 3, 3, 6, 30, tzinfo=tz)
    sunset = datetime(2026, 3, 3, 18, 45, tzinfo=tz)
    window = SunWindow(sunrise=sunrise, sunset=sunset, source="test")

    assert select_day_or_night_band(sunrise, window, "sand", "bronze") == "sand"
    assert select_day_or_night_band(sunset, window, "sand", "bronze") == "bronze"


def test_compute_real_sun_window_returns_none_for_invalid_location():
    tz = ZoneInfo("UTC")
    window = compute_real_sun_window(date(2026, 3, 3), tz, latitude=5000.0, longitude=5000.0)
    assert window is None


def test_resolve_effective_band_explicit():
    now = datetime(2026, 3, 3, 12, 0, tzinfo=ZoneInfo("UTC"))
    decision = resolve_effective_band(
        local_now=now,
        band_mode="tomato",
        day_band="sand",
        night_band="bronze",
        location=None,
        hemisphere="north",
    )
    assert isinstance(decision, BandDecision)
    assert decision.band == "tomato"
    assert decision.source == "explicit"


def test_resolve_effective_band_uses_real_sun_when_available(monkeypatch):
    now = datetime(2026, 3, 3, 12, 0, tzinfo=ZoneInfo("UTC"))
    location = GeoLocation(latitude=40.0, longitude=-73.0, source="env", fetched_at=0.0)
    window = SunWindow(
        sunrise=datetime(2026, 3, 3, 6, 0, tzinfo=ZoneInfo("UTC")),
        sunset=datetime(2026, 3, 3, 18, 0, tzinfo=ZoneInfo("UTC")),
        source="real_sun",
    )
    monkeypatch.setattr("pypixoo.clock_palette.compute_real_sun_window", lambda **kwargs: window)
    decision = resolve_effective_band(
        local_now=now,
        band_mode="auto",
        day_band="sand",
        night_band="bronze",
        location=location,
        hemisphere="north",
    )
    assert decision.band == "sand"
    assert decision.source == "real_sun"
    assert decision.sunrise == window.sunrise


def test_resolve_effective_band_falls_back_to_tz_seasonal(monkeypatch):
    now = datetime(2026, 1, 3, 1, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr("pypixoo.clock_palette.compute_real_sun_window", lambda **kwargs: None)
    decision = resolve_effective_band(
        local_now=now,
        band_mode="auto",
        day_band="sand",
        night_band="bronze",
        location=None,
        hemisphere="north",
    )
    assert decision.source == "tz_seasonal"
    assert decision.band in ("sand", "bronze")

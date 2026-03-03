"""Adaptive band selection helpers for pixooclock."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Mapping, Optional

import requests
from astral import Observer
from astral.sun import sun


IPAPI_URL = "https://ipapi.co/json/"
GEO_CACHE_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class GeoLocation:
    latitude: float
    longitude: float
    source: str
    fetched_at: float


@dataclass(frozen=True)
class SunWindow:
    sunrise: datetime
    sunset: datetime
    source: str


@dataclass(frozen=True)
class BandDecision:
    band: str
    source: str
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None


def _geo_cache_path() -> Path:
    base = Path(os.environ.get("PYPIXOO_LOCK_DIR", os.path.expanduser("~/.pypixoo")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "geolocation.json"


def _coerce_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_geo_cache(path: Path, now_epoch: float, ttl_seconds: int = GEO_CACHE_TTL_SECONDS) -> Optional[GeoLocation]:
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None

    fetched_at = _coerce_float(payload.get("fetched_at"))
    latitude = _coerce_float(payload.get("latitude"))
    longitude = _coerce_float(payload.get("longitude"))
    source = str(payload.get("source") or "cache")
    if fetched_at is None or latitude is None or longitude is None:
        return None
    if now_epoch - fetched_at > ttl_seconds:
        return None
    return GeoLocation(latitude=latitude, longitude=longitude, source=source, fetched_at=fetched_at)


def save_geo_cache(path: Path, location: GeoLocation) -> None:
    payload = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "source": location.source,
        "fetched_at": location.fetched_at,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def fetch_ip_geolocation_ipapi(*, timeout: float = 3.0, now_epoch: Optional[float] = None) -> Optional[GeoLocation]:
    try:
        response = requests.get(IPAPI_URL, timeout=timeout)
        data = response.json()
    except Exception:
        return None

    latitude = _coerce_float(data.get("latitude") or data.get("lat"))
    longitude = _coerce_float(data.get("longitude") or data.get("lon"))
    if latitude is None or longitude is None:
        return None
    fetched_at = now_epoch if now_epoch is not None else datetime.now().timestamp()
    return GeoLocation(latitude=latitude, longitude=longitude, source="ipapi", fetched_at=fetched_at)


def resolve_location(
    *,
    latitude: Optional[float],
    longitude: Optional[float],
    env: Optional[Mapping[str, str]] = None,
    now_epoch: Optional[float] = None,
    cache_path: Optional[Path] = None,
    timeout: float = 3.0,
) -> Optional[GeoLocation]:
    now_epoch = now_epoch if now_epoch is not None else datetime.now().timestamp()
    env_map = env if env is not None else os.environ

    if latitude is not None and longitude is not None:
        return GeoLocation(latitude=float(latitude), longitude=float(longitude), source="cli", fetched_at=now_epoch)

    env_lat = _coerce_float(env_map.get("PIXOO_LATITUDE"))
    env_lon = _coerce_float(env_map.get("PIXOO_LONGITUDE"))
    if env_lat is not None and env_lon is not None:
        return GeoLocation(latitude=env_lat, longitude=env_lon, source="env", fetched_at=now_epoch)

    cache = cache_path if cache_path is not None else _geo_cache_path()
    cached = load_geo_cache(cache, now_epoch=now_epoch)
    if cached is not None:
        return GeoLocation(
            latitude=cached.latitude,
            longitude=cached.longitude,
            source="cache",
            fetched_at=cached.fetched_at,
        )

    fetched = fetch_ip_geolocation_ipapi(timeout=timeout, now_epoch=now_epoch)
    if fetched is None:
        return None
    save_geo_cache(cache, fetched)
    return fetched


def resolve_hemisphere(tz_name: str, env_override: Optional[str] = None) -> str:
    if env_override:
        normalized = env_override.strip().lower()
        if normalized in ("north", "south"):
            return normalized

    south_prefixes = (
        "Australia/",
        "Antarctica/",
        "America/Argentina",
        "America/Santiago",
        "America/Montevideo",
        "America/Sao_Paulo",
        "America/Asuncion",
        "Pacific/Auckland",
        "Pacific/Chatham",
        "Pacific/Fiji",
        "Pacific/Tongatapu",
        "Pacific/Apia",
    )
    for prefix in south_prefixes:
        if tz_name.startswith(prefix):
            return "south"
    return "north"


def compute_real_sun_window(local_date: date, tzinfo, latitude: float, longitude: float) -> Optional[SunWindow]:
    try:
        observer = Observer(latitude=latitude, longitude=longitude)
        values = sun(observer, date=local_date, tzinfo=tzinfo)
    except Exception:
        return None
    sunrise = values.get("sunrise")
    sunset = values.get("sunset")
    if sunrise is None or sunset is None:
        return None
    return SunWindow(sunrise=sunrise, sunset=sunset, source="real_sun")


def _float_hour_to_datetime(local_date: date, tzinfo, hour_float: float) -> datetime:
    hour_float = max(0.0, min(23.9997222222, hour_float))
    whole_hours = int(hour_float)
    minute_float = (hour_float - whole_hours) * 60.0
    whole_minutes = int(minute_float)
    second_float = (minute_float - whole_minutes) * 60.0
    whole_seconds = int(second_float)
    microseconds = int(round((second_float - whole_seconds) * 1_000_000))
    if microseconds == 1_000_000:
        whole_seconds += 1
        microseconds = 0
    return datetime.combine(
        local_date,
        time(hour=whole_hours, minute=whole_minutes, second=whole_seconds, microsecond=microseconds),
        tzinfo=tzinfo,
    )


def compute_seasonal_tz_window(local_dt: datetime, hemisphere: str) -> SunWindow:
    day_of_year = local_dt.timetuple().tm_yday
    solstice_day = 172 if hemisphere == "north" else 355
    phase = (2.0 * math.pi * (day_of_year - solstice_day)) / 365.25
    daylight_hours = 12.0 + (2.5 * math.cos(phase))
    dst = local_dt.dst()
    dst_shift = 1.0 if dst is not None and dst != timedelta(0) else 0.0

    sunrise_hour = 12.0 - (daylight_hours / 2.0) + dst_shift
    sunset_hour = 12.0 + (daylight_hours / 2.0) + dst_shift

    sunrise = _float_hour_to_datetime(local_dt.date(), local_dt.tzinfo, sunrise_hour)
    sunset = _float_hour_to_datetime(local_dt.date(), local_dt.tzinfo, sunset_hour)
    return SunWindow(sunrise=sunrise, sunset=sunset, source="tz_seasonal")


def select_day_or_night_band(local_now: datetime, window: SunWindow, day_band: str, night_band: str) -> str:
    return day_band if window.sunrise <= local_now < window.sunset else night_band


def resolve_effective_band(
    *,
    local_now: datetime,
    band_mode: str,
    day_band: str,
    night_band: str,
    location: Optional[GeoLocation],
    hemisphere: str,
) -> BandDecision:
    if band_mode != "auto":
        return BandDecision(band=band_mode, source="explicit")

    if location is not None:
        real = compute_real_sun_window(
            local_date=local_now.date(),
            tzinfo=local_now.tzinfo,
            latitude=location.latitude,
            longitude=location.longitude,
        )
        if real is not None:
            return BandDecision(
                band=select_day_or_night_band(local_now, real, day_band, night_band),
                source="real_sun",
                sunrise=real.sunrise,
                sunset=real.sunset,
            )

    seasonal = compute_seasonal_tz_window(local_now, hemisphere=hemisphere)
    return BandDecision(
        band=select_day_or_night_band(local_now, seasonal, day_band, night_band),
        source="tz_seasonal",
        sunrise=seasonal.sunrise,
        sunset=seasonal.sunset,
    )

"""Weather client for Tomorrow.io API — provides current conditions."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

log = logging.getLogger(__name__)

_REALTIME_URL = "https://api.tomorrow.io/v4/weather/realtime"
_FORECAST_URL = "https://api.tomorrow.io/v4/weather/forecast"

_WEATHER_CODES = {
    0: "Unbekannt",
    1000: "Klar",
    1100: "Meist klar",
    1101: "Teilweise bewölkt",
    1102: "Meist bewölkt",
    1001: "Bewölkt",
    2000: "Nebel",
    2100: "Leichter Nebel",
    4000: "Nieselregen",
    4001: "Regen",
    4200: "Leichter Regen",
    4201: "Starker Regen",
    5000: "Schnee",
    5001: "Schneeschauer",
    5100: "Leichter Schnee",
    5101: "Starker Schnee",
    6000: "Gefrierender Niesel",
    6001: "Gefrierender Regen",
    6200: "Leichter gefrierender Regen",
    6201: "Starker gefrierender Regen",
    7000: "Eiskörner",
    7101: "Starke Eiskörner",
    7102: "Leichte Eiskörner",
    8000: "Gewitter",
}


@dataclass
class WeatherData:
    temperature_c: float
    humidity: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    weather_code: Optional[int] = None
    condition: str = ""
    visibility_km: Optional[float] = None
    pressure_hpa: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    temperature_apparent_c: Optional[float] = None
    precipitation_probability_pct: Optional[float] = None

    def temperature_str(self, unit: str = "c") -> str:
        if unit == "f":
            return f"{self.temperature_c * 9 / 5 + 32:.0f}°F"
        return f"{self.temperature_c:.0f}°C"

    @property
    def wind_str(self) -> str:
        if self.wind_speed_ms is None:
            return ""
        kt = self.wind_speed_ms * 1.94384
        return f"{kt:.0f}kt"

    def wind_speed_str(self, distance_unit: str = "km") -> str:
        """Wind speed in whichever unit family the display's distance
        setting already uses (km -> km/h, sm -> mph, nm -> kt) -- there's
        no separate wind-unit setting, so it follows distance_unit."""
        if self.wind_speed_ms is None:
            return ""
        if distance_unit == "sm":
            return f"{self.wind_speed_ms * 2.23694:.0f} mph"
        if distance_unit == "nm":
            return f"{self.wind_speed_ms * 1.94384:.0f} kt"
        return f"{self.wind_speed_ms * 3.6:.0f} km/h"


@dataclass
class DailyForecast:
    date: str  # ISO date, "YYYY-MM-DD"
    temp_min_c: float
    temp_max_c: float
    weather_code: Optional[int] = None
    condition: str = ""

    def temp_range_str(self, unit: str = "c") -> str:
        if unit == "f":
            lo = self.temp_min_c * 9 / 5 + 32
            hi = self.temp_max_c * 9 / 5 + 32
            return f"{lo:.0f}° / {hi:.0f}°F"
        return f"{self.temp_min_c:.0f}° / {self.temp_max_c:.0f}°C"


class WeatherClient:
    """Fetches current + forecast weather from Tomorrow.io, each cached
    separately in memory (the forecast changes far less often than
    current conditions, so it gets its own longer-lived cache instead of
    sharing the realtime one)."""

    def __init__(
        self,
        api_key: str,
        lat: float,
        lon: float,
        cache_ttl_s: float = 600.0,
        forecast_cache_ttl_s: float = 1800.0,
    ) -> None:
        self._api_key = api_key
        self._lat = lat
        self._lon = lon
        self._cache_ttl_s = cache_ttl_s
        self._forecast_cache_ttl_s = forecast_cache_ttl_s
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "SassoRadarTower/0.1"
        self._cache: Optional[WeatherData] = None
        self._cache_ts: float = 0.0
        self._last_attempt_ts: float = 0.0
        self._forecast_cache: list[DailyForecast] = []
        self._forecast_cache_ts: float = 0.0
        self._forecast_last_attempt_ts: float = 0.0
        # Tracks the *current-conditions* fetch specifically (not the
        # forecast) -- that's the "right now" data the weather screen
        # shows most prominently, so it's the one that gets an "as of"
        # age hint when a fetch fails and a stale cached value is served
        # instead of a crash.
        self._last_fetch_failed: bool = False

    def get_weather(self) -> Optional[WeatherData]:
        now = time.monotonic()
        if self._cache and (now - self._cache_ts) < self._cache_ttl_s:
            self._last_fetch_failed = False
            return self._cache
        # get_weather() is called every render frame regardless of which
        # screen is active -- without this, a failing fetch (e.g. a rate
        # limit) would be retried every single frame forever, since a
        # failure never used to advance _cache_ts. Reuse the same TTL as
        # a retry backoff for failed attempts.
        if self._last_attempt_ts and (now - self._last_attempt_ts) < self._cache_ttl_s:
            return self._cache
        self._last_attempt_ts = now
        try:
            data = self._fetch()
            self._cache = data
            self._cache_ts = now
            self._last_fetch_failed = False
        except Exception:
            log.exception("Weather fetch failed, returning cached data")
            self._last_fetch_failed = True
        return self._cache

    @property
    def is_stale(self) -> bool:
        """True if the most recent fetch attempt failed -- get_weather()
        is then serving a possibly-old cached value (or None, if nothing
        has ever been fetched successfully)."""
        return self._last_fetch_failed

    def weather_age_s(self) -> Optional[float]:
        """Seconds since the currently-cached WeatherData was actually
        fetched, or None if nothing has ever been fetched. Meaningful
        mainly when is_stale is True; a fresh within-TTL read doesn't
        need an age disclaimer."""
        if self._cache_ts == 0.0:
            return None
        return time.monotonic() - self._cache_ts

    def get_forecast(self, days: int = 3) -> list[DailyForecast]:
        now = time.monotonic()
        if self._forecast_cache and (now - self._forecast_cache_ts) < self._forecast_cache_ttl_s:
            return self._forecast_cache[:days]
        if self._forecast_last_attempt_ts and (now - self._forecast_last_attempt_ts) < self._forecast_cache_ttl_s:
            return self._forecast_cache[:days]
        self._forecast_last_attempt_ts = now
        try:
            data = self._fetch_forecast(days)
            self._forecast_cache = data
            self._forecast_cache_ts = now
        except Exception:
            log.exception("Forecast fetch failed, returning cached data")
        return self._forecast_cache[:days]

    def _fetch(self) -> WeatherData:
        params = {
            "location": f"{self._lat},{self._lon}",
            "apikey": self._api_key,
            "units": "metric",
        }
        resp = self._session.get(_REALTIME_URL, params=params, timeout=10)
        resp.raise_for_status()
        return self._parse(resp.json())

    def _parse(self, data: dict) -> WeatherData:
        values = data.get("data", {}).get("values", {})
        code = values.get("weatherCode")
        return WeatherData(
            temperature_c=float(values.get("temperature", 0)),
            humidity=_opt_float(values, "humidity"),
            wind_speed_ms=_opt_float(values, "windSpeed"),
            wind_direction_deg=_opt_float(values, "windDirection"),
            weather_code=code,
            condition=_WEATHER_CODES.get(code, "") if code is not None else "",
            visibility_km=_opt_float(values, "visibility"),
            pressure_hpa=_opt_float(values, "pressureSeaLevel"),
            cloud_cover_pct=_opt_float(values, "cloudCover"),
            temperature_apparent_c=_opt_float(values, "temperatureApparent"),
            precipitation_probability_pct=_opt_float(values, "precipitationProbability"),
        )

    def _fetch_forecast(self, days: int) -> list[DailyForecast]:
        params = {
            "location": f"{self._lat},{self._lon}",
            "apikey": self._api_key,
            "units": "metric",
            "timesteps": "1d",
        }
        resp = self._session.get(_FORECAST_URL, params=params, timeout=10)
        resp.raise_for_status()
        return self._parse_forecast(resp.json(), days)

    def _parse_forecast(self, data: dict, days: int) -> list[DailyForecast]:
        entries = data.get("timelines", {}).get("daily", [])
        result = []
        for entry in entries[:days]:
            values = entry.get("values", {})
            code = values.get("weatherCodeMax", values.get("weatherCode"))
            result.append(DailyForecast(
                date=(entry.get("time") or "")[:10],
                temp_min_c=float(values.get("temperatureMin", 0)),
                temp_max_c=float(values.get("temperatureMax", 0)),
                weather_code=code,
                condition=_WEATHER_CODES.get(code, "") if code is not None else "",
            ))
        return result

    def close(self) -> None:
        self._session.close()


def _opt_float(d: dict, key: str) -> Optional[float]:
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

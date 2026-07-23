"""Weather client for Tomorrow.io API — provides current conditions."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

log = logging.getLogger(__name__)

_REALTIME_URL = "https://api.tomorrow.io/v4/weather/realtime"

_WEATHER_CODES = {
    0: "Unknown",
    1000: "Clear",
    1100: "Mostly Clear",
    1101: "Partly Cloudy",
    1102: "Mostly Cloudy",
    1001: "Cloudy",
    2000: "Fog",
    2100: "Light Fog",
    4000: "Drizzle",
    4001: "Rain",
    4200: "Light Rain",
    4201: "Heavy Rain",
    5000: "Snow",
    5001: "Flurries",
    5100: "Light Snow",
    5101: "Heavy Snow",
    6000: "Freezing Drizzle",
    6001: "Freezing Rain",
    6200: "Light Freezing Rain",
    6201: "Heavy Freezing Rain",
    7000: "Ice Pellets",
    7101: "Heavy Ice Pellets",
    7102: "Light Ice Pellets",
    8000: "Thunderstorm",
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

    @property
    def temperature_str(self) -> str:
        return f"{self.temperature_c:.0f}°C"

    @property
    def wind_str(self) -> str:
        if self.wind_speed_ms is None:
            return ""
        kt = self.wind_speed_ms * 1.94384
        return f"{kt:.0f}kt"


class WeatherClient:
    """Fetches current weather from Tomorrow.io with in-memory caching."""

    def __init__(
        self,
        api_key: str,
        lat: float,
        lon: float,
        cache_ttl_s: float = 600.0,
    ) -> None:
        self._api_key = api_key
        self._lat = lat
        self._lon = lon
        self._cache_ttl_s = cache_ttl_s
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "SassoRadarTower/0.1"
        self._cache: Optional[WeatherData] = None
        self._cache_ts: float = 0.0

    def get_weather(self) -> Optional[WeatherData]:
        if self._cache and (time.monotonic() - self._cache_ts) < self._cache_ttl_s:
            return self._cache
        try:
            data = self._fetch()
            self._cache = data
            self._cache_ts = time.monotonic()
        except Exception:
            log.exception("Weather fetch failed, returning cached data")
        return self._cache

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
        )

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

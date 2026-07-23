"""Configuration management with priority: env vars > portal settings > defaults."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

_SETTINGS_DIR = Path(os.environ.get(
    "FLUGRADAR_DATA_DIR",
    Path.home() / ".local" / "share" / "flugradar",
))

PORTAL_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"


@dataclass
class HomeLocation:
    lat: float = 47.3769  # Zurich default
    lon: float = 8.5417
    radius_km: float = 100.0


@dataclass
class AdsbConfig:
    base_url: str = "https://opendata.adsb.fi/api/v2"
    poll_interval_s: float = 3.0
    cache_ttl_s: float = 5.0
    request_timeout_s: float = 10.0


@dataclass
class AppSettings:
    home: HomeLocation = field(default_factory=HomeLocation)
    adsb: AdsbConfig = field(default_factory=AdsbConfig)
    distance_unit: str = "km"  # km | sm | nm
    min_altitude_ft: int = 0
    fr24_api_key: str = ""
    tomorrow_api_key: str = ""
    airlabs_api_key: str = ""

    def __post_init__(self) -> None:
        self._apply_env()
        self._apply_portal_settings()

    def _apply_env(self) -> None:
        if v := os.environ.get("FLUGRADAR_HOME_LAT"):
            self.home.lat = float(v)
        if v := os.environ.get("FLUGRADAR_HOME_LON"):
            self.home.lon = float(v)
        if v := os.environ.get("FLUGRADAR_RADIUS_KM"):
            self.home.radius_km = float(v)
        if v := os.environ.get("FLUGRADAR_POLL_INTERVAL"):
            self.adsb.poll_interval_s = float(v)
        if v := os.environ.get("FLUGRADAR_DISTANCE_UNIT"):
            self.distance_unit = v
        if v := os.environ.get("FLUGRADAR_MIN_ALT_FT"):
            self.min_altitude_ft = int(v)
        if v := os.environ.get("FR24_API_KEY"):
            self.fr24_api_key = v
        if v := os.environ.get("TOMORROW_API_KEY"):
            self.tomorrow_api_key = v
        if v := os.environ.get("AIRLABS_API_KEY"):
            self.airlabs_api_key = v

    def _apply_portal_settings(self) -> None:
        if not PORTAL_SETTINGS_FILE.exists():
            return
        try:
            data = json.loads(PORTAL_SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return
        if "home_lat" in data:
            self.home.lat = float(data["home_lat"])
        if "home_lon" in data:
            self.home.lon = float(data["home_lon"])
        if "radius_km" in data:
            self.home.radius_km = float(data["radius_km"])
        if "distance_unit" in data:
            self.distance_unit = data["distance_unit"]
        if "min_altitude_ft" in data:
            self.min_altitude_ft = int(data["min_altitude_ft"])

    def save_portal_settings(self, updates: dict) -> None:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        current: dict = {}
        if PORTAL_SETTINGS_FILE.exists():
            try:
                current = json.loads(PORTAL_SETTINGS_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        current.update(updates)
        PORTAL_SETTINGS_FILE.write_text(json.dumps(current, indent=2))

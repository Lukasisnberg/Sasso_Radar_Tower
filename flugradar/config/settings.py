"""Configuration management with priority: env vars > portal settings > defaults."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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
    theme: str = "dark"  # dark | amber
    aircraft_icon_set: str = "detailed"  # detailed | simple
    min_altitude_ft: int = 0
    auto_clock_s: int = 300
    fr24_api_key: str = ""
    tomorrow_api_key: str = ""
    airlabs_api_key: str = ""

    _portal_mtime: Optional[float] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._apply_portal_settings()
        self._apply_env()
        self._portal_mtime = self._get_portal_mtime()

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
        if v := os.environ.get("FLUGRADAR_THEME"):
            self.theme = v
        if v := os.environ.get("FLUGRADAR_AIRCRAFT_ICON_SET"):
            self.aircraft_icon_set = v
        if v := os.environ.get("FLUGRADAR_MIN_ALT_FT"):
            self.min_altitude_ft = int(v)
        if v := os.environ.get("FLUGRADAR_AUTO_CLOCK_S"):
            self.auto_clock_s = int(v)
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
        self._apply_data(data)

    def _apply_data(self, data: dict) -> None:
        if "home_lat" in data:
            self.home.lat = float(data["home_lat"])
        if "home_lon" in data:
            self.home.lon = float(data["home_lon"])
        if "radius_km" in data:
            self.home.radius_km = float(data["radius_km"])
        if "distance_unit" in data:
            self.distance_unit = data["distance_unit"]
        if "theme" in data:
            self.theme = data["theme"]
        if "aircraft_icon_set" in data:
            self.aircraft_icon_set = data["aircraft_icon_set"]
        if "min_altitude_ft" in data:
            self.min_altitude_ft = int(data["min_altitude_ft"])
        if "auto_clock_s" in data:
            self.auto_clock_s = int(data["auto_clock_s"])

    def _get_portal_mtime(self) -> Optional[float]:
        try:
            return PORTAL_SETTINGS_FILE.stat().st_mtime
        except OSError:
            return None

    def check_portal_reload(self) -> bool:
        """Re-read portal settings if the file changed. Returns True if reloaded."""
        mtime = self._get_portal_mtime()
        if mtime == self._portal_mtime:
            return False
        self._portal_mtime = mtime
        old_theme = self.theme
        old_icon_set = self.aircraft_icon_set
        old_unit = self.distance_unit
        old_lat = self.home.lat
        old_lon = self.home.lon
        old_radius = self.home.radius_km
        old_min_alt = self.min_altitude_ft
        old_auto_clock = self.auto_clock_s

        defaults = HomeLocation()
        self.home.lat = defaults.lat
        self.home.lon = defaults.lon
        self.home.radius_km = defaults.radius_km
        self.distance_unit = "km"
        self.theme = "dark"
        self.aircraft_icon_set = "detailed"
        self.min_altitude_ft = 0
        self.auto_clock_s = 300
        self._apply_portal_settings()
        self._apply_env()

        return (
            self.theme != old_theme
            or self.aircraft_icon_set != old_icon_set
            or self.distance_unit != old_unit
            or self.home.lat != old_lat
            or self.home.lon != old_lon
            or self.home.radius_km != old_radius
            or self.min_altitude_ft != old_min_alt
            or self.auto_clock_s != old_auto_clock
        )

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
        self._apply_data(updates)

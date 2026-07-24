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


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


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
    theme: str = "amber"  # amber | mono
    aircraft_icon_set: str = "detailed"  # detailed | simple
    min_altitude_ft: int = 0
    auto_clock_s: int = 300
    fr24_api_key: str = ""
    tomorrow_api_key: str = ""
    airlabs_api_key: str = ""
    adsbdb_enabled: bool = True  # no key needed; free enrichment fallback
    adsbdb_enrich_nearest: int = 10
    aircraft_photos_enabled: bool = False
    openaip_api_key: str = ""
    openaip_overlay_enabled: bool = True  # only takes effect if a key is set
    map_provider: str = "carto_dark"  # carto_dark | carto_light | osm | none
    rainviewer_enabled: bool = True  # no key needed
    map_brightness: int = 40  # 0-100, dims map tiles under the radar chrome

    # --- Darstellung (device menu "Darstellung") ---
    show_compass: bool = True
    show_sweep: bool = True
    show_aircraft_tags: bool = True

    # --- Filter (device menu "Filter") ---
    highlight_emergency: bool = True
    highlight_military: bool = True
    only_highlighted: bool = False  # show only emergency/military traffic

    # --- Anzeige (device menu "Anzeige") -- software brightness, since a
    # physical backlight sysfs path can't be assumed for every panel/driver.
    brightness: int = 100  # 0-100
    night_mode_enabled: bool = False
    night_mode_start: str = "22:00"  # HH:MM, local time
    night_mode_end: str = "06:00"
    night_mode_brightness: int = 30  # 0-100, applied instead of `brightness` in the window

    # --- Einheiten (device menu "Einheiten") ---
    temperature_unit: str = "c"  # c | f
    time_format: str = "24h"  # 24h | 12h

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
        if v := os.environ.get("ADSBDB_ENABLED"):
            self.adsbdb_enabled = _parse_bool(v)
        if v := os.environ.get("ADSBDB_ENRICH_NEAREST"):
            self.adsbdb_enrich_nearest = int(v)
        if v := os.environ.get("AIRCRAFT_PHOTOS_ENABLED"):
            self.aircraft_photos_enabled = _parse_bool(v)
        if v := os.environ.get("OPENAIP_API_KEY"):
            self.openaip_api_key = v
        if v := os.environ.get("OPENAIP_OVERLAY_ENABLED"):
            self.openaip_overlay_enabled = _parse_bool(v)
        if v := os.environ.get("MAP_PROVIDER"):
            self.map_provider = v
        if v := os.environ.get("RAINVIEWER_ENABLED"):
            self.rainviewer_enabled = _parse_bool(v)
        if v := os.environ.get("MAP_BRIGHTNESS"):
            self.map_brightness = int(v)
        if v := os.environ.get("FLUGRADAR_SHOW_COMPASS"):
            self.show_compass = _parse_bool(v)
        if v := os.environ.get("FLUGRADAR_SHOW_SWEEP"):
            self.show_sweep = _parse_bool(v)
        if v := os.environ.get("FLUGRADAR_SHOW_AIRCRAFT_TAGS"):
            self.show_aircraft_tags = _parse_bool(v)
        if v := os.environ.get("FLUGRADAR_HIGHLIGHT_EMERGENCY"):
            self.highlight_emergency = _parse_bool(v)
        if v := os.environ.get("FLUGRADAR_HIGHLIGHT_MILITARY"):
            self.highlight_military = _parse_bool(v)
        if v := os.environ.get("FLUGRADAR_ONLY_HIGHLIGHTED"):
            self.only_highlighted = _parse_bool(v)
        if v := os.environ.get("FLUGRADAR_BRIGHTNESS"):
            self.brightness = int(v)
        if v := os.environ.get("FLUGRADAR_NIGHT_MODE_ENABLED"):
            self.night_mode_enabled = _parse_bool(v)
        if v := os.environ.get("FLUGRADAR_NIGHT_MODE_START"):
            self.night_mode_start = v
        if v := os.environ.get("FLUGRADAR_NIGHT_MODE_END"):
            self.night_mode_end = v
        if v := os.environ.get("FLUGRADAR_NIGHT_MODE_BRIGHTNESS"):
            self.night_mode_brightness = int(v)
        if v := os.environ.get("FLUGRADAR_TEMPERATURE_UNIT"):
            self.temperature_unit = v
        if v := os.environ.get("FLUGRADAR_TIME_FORMAT"):
            self.time_format = v

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
        if "adsbdb_enabled" in data:
            self.adsbdb_enabled = _parse_bool(data["adsbdb_enabled"])
        if "adsbdb_enrich_nearest" in data:
            self.adsbdb_enrich_nearest = int(data["adsbdb_enrich_nearest"])
        if "aircraft_photos_enabled" in data:
            self.aircraft_photos_enabled = _parse_bool(data["aircraft_photos_enabled"])
        if "openaip_api_key" in data:
            self.openaip_api_key = data["openaip_api_key"]
        if "openaip_overlay_enabled" in data:
            self.openaip_overlay_enabled = _parse_bool(data["openaip_overlay_enabled"])
        if "map_provider" in data:
            self.map_provider = data["map_provider"]
        if "rainviewer_enabled" in data:
            self.rainviewer_enabled = _parse_bool(data["rainviewer_enabled"])
        if "map_brightness" in data:
            self.map_brightness = int(data["map_brightness"])
        if "show_compass" in data:
            self.show_compass = _parse_bool(data["show_compass"])
        if "show_sweep" in data:
            self.show_sweep = _parse_bool(data["show_sweep"])
        if "show_aircraft_tags" in data:
            self.show_aircraft_tags = _parse_bool(data["show_aircraft_tags"])
        if "highlight_emergency" in data:
            self.highlight_emergency = _parse_bool(data["highlight_emergency"])
        if "highlight_military" in data:
            self.highlight_military = _parse_bool(data["highlight_military"])
        if "only_highlighted" in data:
            self.only_highlighted = _parse_bool(data["only_highlighted"])
        if "brightness" in data:
            self.brightness = int(data["brightness"])
        if "night_mode_enabled" in data:
            self.night_mode_enabled = _parse_bool(data["night_mode_enabled"])
        if "night_mode_start" in data:
            self.night_mode_start = data["night_mode_start"]
        if "night_mode_end" in data:
            self.night_mode_end = data["night_mode_end"]
        if "night_mode_brightness" in data:
            self.night_mode_brightness = int(data["night_mode_brightness"])
        if "temperature_unit" in data:
            self.temperature_unit = data["temperature_unit"]
        if "time_format" in data:
            self.time_format = data["time_format"]

    def _get_portal_mtime(self) -> Optional[float]:
        try:
            return PORTAL_SETTINGS_FILE.stat().st_mtime
        except OSError:
            return None

    def mark_portal_synced(self) -> None:
        """Call after writing settings.json from *this* process (the
        on-device menu) so the next check_portal_reload() doesn't treat our
        own write as an external change and redundantly re-apply it --
        harmless in principle, but it rebuilds the map compositor and would
        visibly flicker for no reason."""
        self._portal_mtime = self._get_portal_mtime()

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
        old_adsbdb_enabled = self.adsbdb_enabled
        old_adsbdb_nearest = self.adsbdb_enrich_nearest
        old_photos_enabled = self.aircraft_photos_enabled
        old_openaip_overlay = self.openaip_overlay_enabled
        old_map_provider = self.map_provider
        old_rainviewer_enabled = self.rainviewer_enabled
        old_map_brightness = self.map_brightness
        old_show_compass = self.show_compass
        old_show_sweep = self.show_sweep
        old_show_aircraft_tags = self.show_aircraft_tags
        old_highlight_emergency = self.highlight_emergency
        old_highlight_military = self.highlight_military
        old_only_highlighted = self.only_highlighted
        old_brightness = self.brightness
        old_night_mode_enabled = self.night_mode_enabled
        old_night_mode_start = self.night_mode_start
        old_night_mode_end = self.night_mode_end
        old_night_mode_brightness = self.night_mode_brightness
        old_temperature_unit = self.temperature_unit
        old_time_format = self.time_format

        defaults = HomeLocation()
        self.home.lat = defaults.lat
        self.home.lon = defaults.lon
        self.home.radius_km = defaults.radius_km
        self.distance_unit = "km"
        self.theme = "amber"
        self.aircraft_icon_set = "detailed"
        self.min_altitude_ft = 0
        self.auto_clock_s = 300
        self.adsbdb_enabled = True
        self.adsbdb_enrich_nearest = 10
        self.aircraft_photos_enabled = False
        self.openaip_overlay_enabled = True
        self.map_provider = "carto_dark"
        self.rainviewer_enabled = True
        self.map_brightness = 40
        self.show_compass = True
        self.show_sweep = True
        self.show_aircraft_tags = True
        self.highlight_emergency = True
        self.highlight_military = True
        self.only_highlighted = False
        self.brightness = 100
        self.night_mode_enabled = False
        self.night_mode_start = "22:00"
        self.night_mode_end = "06:00"
        self.night_mode_brightness = 30
        self.temperature_unit = "c"
        self.time_format = "24h"
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
            or self.adsbdb_enabled != old_adsbdb_enabled
            or self.adsbdb_enrich_nearest != old_adsbdb_nearest
            or self.aircraft_photos_enabled != old_photos_enabled
            or self.openaip_overlay_enabled != old_openaip_overlay
            or self.map_provider != old_map_provider
            or self.rainviewer_enabled != old_rainviewer_enabled
            or self.map_brightness != old_map_brightness
            or self.show_compass != old_show_compass
            or self.show_sweep != old_show_sweep
            or self.show_aircraft_tags != old_show_aircraft_tags
            or self.highlight_emergency != old_highlight_emergency
            or self.highlight_military != old_highlight_military
            or self.only_highlighted != old_only_highlighted
            or self.brightness != old_brightness
            or self.night_mode_enabled != old_night_mode_enabled
            or self.night_mode_start != old_night_mode_start
            or self.night_mode_end != old_night_mode_end
            or self.night_mode_brightness != old_night_mode_brightness
            or self.temperature_unit != old_temperature_unit
            or self.time_format != old_time_format
        )

    def save_portal_settings(self, updates: dict) -> None:
        """Merge `updates` into settings.json. Used by both the web portal
        and the on-device menu, so writes are atomic (write to a temp file,
        then rename) -- a concurrent reader must never see a half-written
        file, whichever of the two wrote last."""
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        current: dict = {}
        if PORTAL_SETTINGS_FILE.exists():
            try:
                current = json.loads(PORTAL_SETTINGS_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        current.update(updates)
        tmp_path = PORTAL_SETTINGS_FILE.with_suffix(PORTAL_SETTINGS_FILE.suffix + ".tmp")
        tmp_path.write_text(json.dumps(current, indent=2))
        os.replace(tmp_path, PORTAL_SETTINGS_FILE)
        self._apply_data(updates)

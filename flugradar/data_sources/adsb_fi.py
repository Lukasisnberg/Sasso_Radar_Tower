"""Client for the adsb.fi public ADS-B REST API with in-memory caching."""

import logging
import time
from typing import Optional

import requests

from flugradar.config.settings import AdsbConfig, HomeLocation
from flugradar.data_sources.geo import bearing_deg, haversine_km
from flugradar.data_sources.models import Aircraft

log = logging.getLogger(__name__)

_NAUTICAL_MILES_PER_KM = 0.539957


class AdsbFiClient:
    """Fetches live aircraft positions from api.adsb.fi and caches them."""

    def __init__(self, adsb_cfg: AdsbConfig, home: HomeLocation) -> None:
        self._cfg = adsb_cfg
        self._home = home
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "SassoRadarTower/0.1"
        self._cache: list[Aircraft] = []
        self._cache_ts: float = 0.0

    @property
    def _cache_valid(self) -> bool:
        return (time.monotonic() - self._cache_ts) < self._cfg.cache_ttl_s

    def get_aircraft(self, force_refresh: bool = False) -> list[Aircraft]:
        if self._cache_valid and not force_refresh:
            return self._cache
        try:
            aircraft = self._fetch()
            self._cache = aircraft
            self._cache_ts = time.monotonic()
        except Exception:
            log.exception("adsb.fi fetch failed, returning cached data")
        return self._cache

    def _fetch(self) -> list[Aircraft]:
        radius_nm = self._home.radius_km * _NAUTICAL_MILES_PER_KM
        url = (
            f"{self._cfg.base_url}/lat/{self._home.lat}/lon/{self._home.lon}"
            f"/dist/{radius_nm:.0f}"
        )
        log.debug("GET %s", url)
        resp = self._session.get(url, timeout=self._cfg.request_timeout_s)
        resp.raise_for_status()
        data = resp.json()
        return self._parse(data)

    def _parse(self, data: dict) -> list[Aircraft]:
        results: list[Aircraft] = []
        for ac in data.get("ac", []):
            lat = _float(ac, "lat")
            lon = _float(ac, "lon")
            if lat is None or lon is None:
                continue

            dist = haversine_km(self._home.lat, self._home.lon, lat, lon)
            brng = bearing_deg(self._home.lat, self._home.lon, lat, lon)

            aircraft = Aircraft(
                icao_hex=ac.get("hex", "").strip(),
                lat=lat,
                lon=lon,
                altitude_ft=_int(ac, "alt_baro") or _int(ac, "alt_geom"),
                ground_speed_kt=_float(ac, "gs"),
                track_deg=_float(ac, "track"),
                vertical_rate_fpm=_int(ac, "baro_rate") or _int(ac, "geom_rate"),
                squawk=ac.get("squawk"),
                callsign=(ac.get("flight") or "").strip() or None,
                registration=ac.get("r"),
                aircraft_type=ac.get("t"),
                is_on_ground=bool(ac.get("alt_baro") == "ground"),
                last_seen_s=_float(ac, "seen") or 0.0,
                distance_km=dist,
                bearing_deg=brng,
                category=ac.get("category"),
            )
            results.append(aircraft)

        results.sort(key=lambda a: a.distance_km or float("inf"))
        return results

    def close(self) -> None:
        self._session.close()


def _float(d: dict, key: str) -> Optional[float]:
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _int(d: dict, key: str) -> Optional[int]:
    v = d.get(key)
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None

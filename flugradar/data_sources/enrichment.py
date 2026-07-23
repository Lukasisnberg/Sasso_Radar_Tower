"""Flight data enrichment via AirLabs API — adds airline, route, flight number."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from flugradar.data_sources.models import Aircraft

log = logging.getLogger(__name__)

_AIRLABS_BASE = "https://airlabs.co/api/v9"


@dataclass
class FlightInfo:
    airline_name: Optional[str] = None
    airline_iata: Optional[str] = None
    flight_iata: Optional[str] = None
    dep_iata: Optional[str] = None
    arr_iata: Optional[str] = None


class EnrichmentClient:
    """Enriches aircraft with airline/route data from AirLabs."""

    def __init__(self, api_key: str, cache_ttl_s: float = 300.0) -> None:
        self._api_key = api_key
        self._cache_ttl_s = cache_ttl_s
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "SassoRadarTower/0.1"
        self._cache: dict[str, tuple[float, Optional[FlightInfo]]] = {}

    def enrich(self, aircraft: list[Aircraft]) -> None:
        for ac in aircraft:
            if ac.airline and ac.origin:
                continue
            info = self._get_flight_info(ac.icao_hex)
            if info:
                if info.airline_name and not ac.airline:
                    ac.airline = info.airline_name
                if info.flight_iata and not ac.flight_number:
                    ac.flight_number = info.flight_iata
                if info.dep_iata and not ac.origin:
                    ac.origin = info.dep_iata
                if info.arr_iata and not ac.destination:
                    ac.destination = info.arr_iata

    def _get_flight_info(self, icao_hex: str) -> Optional[FlightInfo]:
        now = time.monotonic()
        if icao_hex in self._cache:
            ts, info = self._cache[icao_hex]
            if (now - ts) < self._cache_ttl_s:
                return info

        try:
            info = self._fetch(icao_hex)
        except Exception:
            log.debug("AirLabs lookup failed for %s", icao_hex)
            info = None

        self._cache[icao_hex] = (now, info)
        self._prune_cache(now)
        return info

    def _fetch(self, icao_hex: str) -> Optional[FlightInfo]:
        resp = self._session.get(
            f"{_AIRLABS_BASE}/flights",
            params={"api_key": self._api_key, "hex": icao_hex},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        flights = data.get("response", [])
        if not flights:
            return None
        f = flights[0]
        return FlightInfo(
            airline_name=f.get("airline_name"),
            airline_iata=f.get("airline_iata"),
            flight_iata=f.get("flight_iata"),
            dep_iata=f.get("dep_iata"),
            arr_iata=f.get("arr_iata"),
        )

    def _prune_cache(self, now: float) -> None:
        if len(self._cache) <= 200:
            return
        expired = [k for k, (ts, _) in self._cache.items() if (now - ts) >= self._cache_ttl_s]
        for k in expired:
            del self._cache[k]

    def close(self) -> None:
        self._session.close()

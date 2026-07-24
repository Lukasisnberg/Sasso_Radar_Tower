"""Flight data enrichment: AirLabs (paid, optional) or adsbdb (free, default).

Single enrichment layer with one clear source priority, used by the
display app instead of talking to either backend directly:

    1. AirLabs, if an API key is configured (kept exactly as before).
    2. adsbdb (flugradar.data_sources.adsbdb), otherwise — free, no key.
    3. No enrichment at all, if neither is available.

This is a global, per-apparatus choice (whichever source is configured
handles *all* aircraft), not a per-aircraft fallback chain -- matching
"mit FR24-Key gewinnt FR24, ohne Key wird adsbdb genutzt".

adsb.fi itself is untouched by any of this: it is the sole, exclusive
source of positions, never routed through here.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests

from flugradar.data_sources.adsbdb import AdsbdbClient, AdsbdbResult
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


class AdsbdbEnricher:
    """Background-threaded adsbdb lookups: throttled, priority-aware.

    A single worker thread processes lookups **one at a time** (never in
    parallel), so a burst of newly-visible aircraft never floods adsbdb
    with simultaneous requests. Reading cached results (`apply`) never
    blocks; a network hiccup mid-lookup just leaves an aircraft
    un-enriched for this cycle, never crashes or stalls the caller.
    """

    def __init__(self, client: AdsbdbClient) -> None:
        self._client = client
        self._priority_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._results: dict[str, AdsbdbResult] = {}
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def request(self, icao_hex: str, callsign: str = "", priority: bool = False) -> None:
        hex_id = (icao_hex or "").strip().lower()
        if not hex_id:
            return
        with self._lock:
            if hex_id in self._pending:
                return
            self._pending.add(hex_id)
        (self._priority_queue if priority else self._queue).put((hex_id, callsign))

    def get_cached(self, icao_hex: str) -> Optional[AdsbdbResult]:
        return self._results.get((icao_hex or "").strip().lower())

    def enrich_priority(self, ac: Aircraft) -> None:
        """Enrich exactly this aircraft with priority (e.g. detail view opened)."""
        self.request(ac.icao_hex, ac.callsign or "", priority=True)

    def enrich_nearest(self, aircraft: list[Aircraft], limit: int) -> None:
        """Queue background lookups for up to `limit` nearest unknown aircraft."""
        candidates = [ac for ac in aircraft if self.get_cached(ac.icao_hex) is None]
        candidates.sort(
            key=lambda ac: ac.distance_km if ac.distance_km is not None else float("inf")
        )
        for ac in candidates[:limit]:
            self.request(ac.icao_hex, ac.callsign or "", priority=False)

    def apply(self, aircraft: list[Aircraft]) -> None:
        """Copy any cached adsbdb results onto matching aircraft. Never blocks."""
        for ac in aircraft:
            result = self.get_cached(ac.icao_hex)
            if result is None:
                continue
            if result.aircraft:
                if not ac.aircraft_type and result.aircraft.icao_type:
                    ac.aircraft_type = result.aircraft.icao_type
                if not ac.registered_owner and result.aircraft.registered_owner:
                    ac.registered_owner = result.aircraft.registered_owner
            if result.route:
                if not ac.airline and result.route.airline:
                    ac.airline = result.route.airline.name
                    if result.route.airline.icao:
                        ac.airline_icao = result.route.airline.icao
                if not ac.flight_number:
                    ac.flight_number = result.route.callsign_iata or result.route.callsign or None
                if not ac.origin and result.route.origin:
                    ac.origin = result.route.origin.iata_code or result.route.origin.icao_code or None
                if not ac.destination and result.route.destination:
                    ac.destination = (
                        result.route.destination.iata_code
                        or result.route.destination.icao_code
                        or None
                    )

    def _worker(self) -> None:
        while not self._stop.is_set():
            hex_id, callsign = self._next_job()
            if hex_id is None:
                continue
            try:
                self._results[hex_id] = self._client.lookup(hex_id, callsign)
            except Exception:
                log.debug("adsbdb background lookup crashed for %s", hex_id, exc_info=True)
            finally:
                with self._lock:
                    self._pending.discard(hex_id)

    def _next_job(self) -> tuple[Optional[str], str]:
        try:
            return self._priority_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            return self._queue.get(timeout=0.5)
        except queue.Empty:
            return None, ""

    def close(self) -> None:
        self._stop.set()
        self._client.close()


class FlightEnrichment:
    """Single entry point the display app talks to for enrichment.

    Picks AirLabs or adsbdb per the module-level priority rule (never
    both, never per-aircraft mixing) and exposes the two access patterns
    the app needs: a cheap per-cycle `poll()` and an on-demand
    `enrich_now()` for whichever aircraft's detail view is open.
    """

    def __init__(
        self,
        airlabs_client: Optional[EnrichmentClient] = None,
        adsbdb_enricher: Optional[AdsbdbEnricher] = None,
    ) -> None:
        self._airlabs = airlabs_client
        self._adsbdb = adsbdb_enricher

    @property
    def using_adsbdb(self) -> bool:
        return self._airlabs is None and self._adsbdb is not None

    def poll(self, aircraft: list[Aircraft], nearest_limit: int = 10) -> None:
        if self._airlabs:
            self._airlabs.enrich(aircraft)
            return
        if self._adsbdb:
            self._adsbdb.apply(aircraft)
            self._adsbdb.enrich_nearest(aircraft, nearest_limit)

    def enrich_now(self, ac: Aircraft) -> None:
        if self._airlabs:
            self._airlabs.enrich([ac])
        elif self._adsbdb:
            self._adsbdb.enrich_priority(ac)
            self._adsbdb.apply([ac])

    def get_adsbdb_photo_urls(self, icao_hex: str) -> Optional[tuple[str, str]]:
        """Returns (thumbnail_url, full_url) from a cached adsbdb result, if any."""
        if not self._adsbdb:
            return None
        result = self._adsbdb.get_cached(icao_hex)
        if result is None or result.aircraft is None:
            return None
        return (
            result.aircraft.url_photo_thumbnail or "",
            result.aircraft.url_photo or "",
        )

    def close(self) -> None:
        if self._airlabs:
            self._airlabs.close()
        if self._adsbdb:
            self._adsbdb.close()

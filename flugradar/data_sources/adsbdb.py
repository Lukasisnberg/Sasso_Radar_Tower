"""Aircraft/route/airline enrichment via adsbdb.com — free, no API key.

adsbdb is a pure enrichment layer on top of adsb.fi: it never supplies
positions and is never used for anything but answering "what/whose is
this aircraft, and where is it going" for a hex/callsign adsb.fi already
reported. adsb.fi remains the sole, unmodified position source.

API base URL: the docs at https://github.com/mrjackwills/adsbdb use a
`/v[semver.major]/` placeholder in every path. Checked empirically against
the live API on 2026-07-24 (repo release at the time: v0.6.5):
`https://api.adsbdb.com/v0/...` returns real data (HTTP 200), while
`/v1/...` and `/v2/...` currently 301-redirect elsewhere. So the current
major version is **v0**, not v1 — re-verify this constant if adsbdb ever
ships a v1.

ROUTE DATA LICENSE (verbatim from the adsbdb README, must not be lost):
"The flight route data is the work of David Taylor, Edinburgh and Jim
Mason, Glasgow, and may not be copied, published, or incorporated into
other databases without the explicit permission of David J Taylor,
Edinburgh." Consequently: route data (AdsbdbRoute and everything nested
in it) is cached **only in RAM with a TTL**, never written to disk, and
no local database/table of routes is ever built up over time. Aircraft
master data (type/owner/registration) isn't covered by that restriction,
but is treated the same way here for simplicity.

Aircraft photos (`url_photo`/`url_photo_thumbnail`) are credited by
adsbdb only with a blanket "airport-data for aircraft photographs" note
in the README's thanks section — the API response itself carries no
per-photo photographer/copyright field (unlike planespotters.net, which
does). See flugradar/data_sources/aircraft_photo.py for the richer,
attributed photo source; adsbdb photos are only ever used as a fallback
when that one has nothing and AIRCRAFT_PHOTOS_ENABLED is explicitly on.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

log = logging.getLogger(__name__)

_BASE_URL = "https://api.adsbdb.com/v0"
_UA = "SassoRadarTower/1.0 (+https://github.com/Lukasisnberg/Sasso_Radar_Tower)"


@dataclass
class AdsbdbAircraft:
    type: str = ""
    icao_type: str = ""
    manufacturer: str = ""
    mode_s: str = ""
    registration: str = ""
    registered_owner: str = ""
    registered_owner_country_name: str = ""
    registered_owner_country_iso_name: str = ""
    registered_owner_operator_flag_code: str = ""
    url_photo: Optional[str] = None
    url_photo_thumbnail: Optional[str] = None


@dataclass
class AdsbdbAirport:
    icao_code: str = ""
    iata_code: str = ""
    name: str = ""
    municipality: str = ""
    country_name: str = ""
    country_iso_name: str = ""


@dataclass
class AdsbdbAirline:
    name: str = ""
    icao: str = ""
    iata: str = ""
    country: str = ""
    country_iso: str = ""
    callsign: str = ""


@dataclass
class AdsbdbRoute:
    callsign: str = ""
    callsign_icao: str = ""
    callsign_iata: str = ""
    airline: Optional[AdsbdbAirline] = None
    origin: Optional[AdsbdbAirport] = None
    destination: Optional[AdsbdbAirport] = None
    midpoint: Optional[AdsbdbAirport] = None


@dataclass
class AdsbdbResult:
    aircraft: Optional[AdsbdbAircraft] = None
    route: Optional[AdsbdbRoute] = None


def _normalize_hex(value: str) -> str:
    return (value or "").strip().lower()


def _normalize_callsign(value: str) -> str:
    return (value or "").strip().upper()


def _parse_airport(data: Optional[dict]) -> Optional[AdsbdbAirport]:
    if not isinstance(data, dict):
        return None
    return AdsbdbAirport(
        icao_code=data.get("icao_code") or "",
        iata_code=data.get("iata_code") or "",
        name=data.get("name") or "",
        municipality=data.get("municipality") or "",
        country_name=data.get("country_name") or "",
        country_iso_name=data.get("country_iso_name") or "",
    )


def _parse_airline(data: Optional[dict]) -> Optional[AdsbdbAirline]:
    if not isinstance(data, dict):
        return None
    return AdsbdbAirline(
        name=data.get("name") or "",
        icao=data.get("icao") or "",
        iata=data.get("iata") or "",
        country=data.get("country") or "",
        country_iso=data.get("country_iso") or "",
        callsign=data.get("callsign") or "",
    )


def _parse_aircraft(data: Optional[dict]) -> Optional[AdsbdbAircraft]:
    if not isinstance(data, dict):
        return None
    return AdsbdbAircraft(
        type=data.get("type") or "",
        icao_type=data.get("icao_type") or "",
        manufacturer=data.get("manufacturer") or "",
        mode_s=data.get("mode_s") or "",
        registration=data.get("registration") or "",
        registered_owner=data.get("registered_owner") or "",
        registered_owner_country_name=data.get("registered_owner_country_name") or "",
        registered_owner_country_iso_name=data.get("registered_owner_country_iso_name") or "",
        registered_owner_operator_flag_code=data.get("registered_owner_operator_flag_code") or "",
        url_photo=data.get("url_photo"),
        url_photo_thumbnail=data.get("url_photo_thumbnail"),
    )


def _parse_route(data: Optional[dict]) -> Optional[AdsbdbRoute]:
    if not isinstance(data, dict):
        return None
    return AdsbdbRoute(
        callsign=data.get("callsign") or "",
        callsign_icao=data.get("callsign_icao") or "",
        callsign_iata=data.get("callsign_iata") or "",
        airline=_parse_airline(data.get("airline")),
        origin=_parse_airport(data.get("origin")),
        destination=_parse_airport(data.get("destination")),
        midpoint=_parse_airport(data.get("midpoint")),
    )


class AdsbdbClient:
    """Synchronous adsbdb.com client with RAM-only, dual-TTL caching.

    Uses the combined `/aircraft/<hex>?callsign=<callsign>` endpoint so a
    single HTTP request can satisfy both the (long-TTL) aircraft cache and
    the (medium-TTL) route cache. Network failures never touch the cache
    or raise — callers get back whatever was last known (possibly
    nothing), so a network outage can't crash or stall the caller.
    """

    def __init__(
        self,
        aircraft_ttl_s: float = 6 * 3600.0,
        route_ttl_s: float = 45 * 60.0,
        negative_ttl_s: float = 300.0,
        timeout_s: float = 8.0,
    ) -> None:
        self._aircraft_ttl_s = aircraft_ttl_s
        self._route_ttl_s = route_ttl_s
        self._negative_ttl_s = negative_ttl_s
        self._timeout_s = timeout_s
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _UA
        self._aircraft_cache: dict[str, tuple[float, Optional[AdsbdbAircraft]]] = {}
        self._route_cache: dict[str, tuple[float, Optional[AdsbdbRoute]]] = {}

    def lookup(self, icao_hex: str, callsign: str = "") -> AdsbdbResult:
        hex_id = _normalize_hex(icao_hex)
        if not hex_id:
            return AdsbdbResult()
        cs = _normalize_callsign(callsign)
        now = time.monotonic()

        aircraft, aircraft_fresh = self._cache_get(self._aircraft_cache, hex_id, now, self._aircraft_ttl_s)
        route: Optional[AdsbdbRoute] = None
        route_fresh = True
        if cs:
            route, route_fresh = self._cache_get(self._route_cache, cs, now, self._route_ttl_s)

        if aircraft_fresh and route_fresh:
            return AdsbdbResult(aircraft=aircraft, route=route)

        try:
            fetched_aircraft, fetched_route, route_conclusive = self._fetch(hex_id, cs)
        except (requests.RequestException, ValueError) as exc:
            log.debug("adsbdb lookup failed for %s: %s", hex_id, exc)
            return AdsbdbResult(aircraft=aircraft, route=route)

        self._aircraft_cache[hex_id] = (now, fetched_aircraft)
        if cs and route_conclusive:
            self._route_cache[cs] = (now, fetched_route)

        return AdsbdbResult(aircraft=fetched_aircraft, route=fetched_route if cs else None)

    def _cache_get(
        self,
        cache: dict[str, tuple[float, Optional[object]]],
        key: str,
        now: float,
        positive_ttl_s: float,
    ) -> tuple[Optional[object], bool]:
        entry = cache.get(key)
        if entry is None:
            return None, False
        ts, value = entry
        ttl = positive_ttl_s if value is not None else self._negative_ttl_s
        return value, (now - ts) < ttl

    def _fetch(
        self, hex_id: str, callsign: str,
    ) -> tuple[Optional[AdsbdbAircraft], Optional[AdsbdbRoute], bool]:
        """Returns (aircraft, route, route_conclusive).

        The adsbdb docs say an unknown callsign on the combined endpoint
        still returns HTTP 200 with just the aircraft part. Empirically it
        can *also* 404 with `{"response": "unknown callsign"}` for some
        well-formed-but-unmatched callsigns (verified 2026-07-24) — while a
        genuinely unknown *aircraft* always 404s with
        `{"response": "unknown aircraft"}`, regardless of the callsign
        param. So an "unknown callsign" 404 must not be treated as the
        aircraft being unknown: we re-fetch the aircraft alone so a bad
        callsign can never poison the aircraft cache. `route_conclusive`
        tells the caller whether the callsign question was actually
        answered (False after this fallback, since we didn't learn
        anything new about the callsign itself beyond "not this way").
        """
        params = {"callsign": callsign} if callsign else None
        resp = self._session.get(
            f"{_BASE_URL}/aircraft/{hex_id}", params=params, timeout=self._timeout_s,
        )

        if resp.status_code == 404:
            if callsign and self._error_reason(resp) == "unknown callsign":
                aircraft, _, _ = self._fetch(hex_id, "")
                return aircraft, None, False
            return None, None, True

        resp.raise_for_status()
        data = resp.json()
        resp_obj = data.get("response") if isinstance(data, dict) else None
        if not isinstance(resp_obj, dict):
            return None, None, True
        aircraft = _parse_aircraft(resp_obj.get("aircraft"))
        route = _parse_route(resp_obj.get("flightroute"))
        return aircraft, route, bool(callsign)

    @staticmethod
    def _error_reason(resp: requests.Response) -> Optional[str]:
        try:
            data = resp.json()
        except ValueError:
            return None
        return data.get("response") if isinstance(data, dict) else None

    def close(self) -> None:
        self._session.close()

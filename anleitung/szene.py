"""Feste, deterministische Beispieldaten für die Buch-Screenshots.

Bewusst *keine* Wiederverwendung von `flugradar.data_sources.demo.DemoSource`
-- die nutzt ungeseedetes `random` für Position/Callsign/Typ, was für ein
Buch, das sich zweimal identisch aufbauen lassen muss, unbrauchbar ist.
Stattdessen wird hier jedes Flugzeug einzeln mit einer festen Peilung und
Entfernung vom Heimatstandort platziert -- reproduzierbar, aber trotzdem
über eine einfache Geo-Formel statt Pixel für Pixel von Hand ausgerechnet.

Heimatstandort: Sassofortino (siehe `flugradar/config/locations.py`), damit
die Beispiele zum zweiten Standort-Preset passen und nicht mit dem
`HomeLocation`-Default (Zürich) kollidieren.
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from dataclasses import dataclass

from flugradar.config.locations import LOCATIONS, resolve_location
from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.weather import DailyForecast, WeatherData

HOME = resolve_location("sassofortino")
assert HOME is not None
HOME_LAT, HOME_LON = HOME.lat, HOME.lon

# Fester Sweep-/Blink-Zeitpunkt für alle Screenshots -- siehe frozen_time()
# unten. Ergibt einen Sweep-Winkel von genau 90° (renderer.py: sweep_angle()
# = (t % 10s) / 10s * 360, hier also exakt am Osten stehend) und eine
# stillstehende, "an"-Phase des Alarmblinkens (renderer.py blinkt mit 3/4 Hz
# über sin(t * ...), t=0 liegt im positiven Halbzyklus).
FROZEN_MONOTONIC = 1_000.0


def _offset(bearing_deg: float, dist_km: float) -> tuple[float, float]:
    """Peilung + Entfernung vom Heimatstandort -> lat/lon.

    Gleiche äquirektangulare Näherung wie
    `flugradar.data_sources.projection.ScreenProjection` -- für die hier
    verwendeten Entfernungen (<= 300 km) ausreichend genau, und es ist
    wichtig, dass die Beispielflugzeuge genau dort erscheinen, wo man sie
    aus Peilung/Entfernung erwarten würde.
    """
    rad = math.radians(bearing_deg)
    dlat = (dist_km / 111.32) * math.cos(rad)
    dlon = (dist_km / (111.32 * math.cos(math.radians(HOME_LAT)))) * math.sin(rad)
    return HOME_LAT + dlat, HOME_LON + dlon


@dataclass(frozen=True)
class _Spec:
    hex_id: str
    callsign: str
    ac_type: str
    bearing: float
    dist_km: float
    alt_ft: int
    speed_kt: float
    heading: float
    vs_fpm: int = 0
    squawk: str = "1200"
    airline: str = ""
    registered_owner: str = ""


# Vierzehn Flugzeuge, handgesetzt (keine Zufallszahlen) -- Mischung aus
# Airline-Jets, einem Turboprop, einem Helikopter, einem GA-Flugzeug und
# den beiden Sonderfällen (Notfall-Squawk, Militär), die die Legendenseite
# (S. 27) braucht.
_SPECS: tuple[_Spec, ...] = (
    _Spec("3c6444", "DLH9MC", "A21N", 20, 38, 34000, 430, 205, -300, airline="Lufthansa"),
    _Spec("400f9a", "BAW28X", "B77W", 65, 72, 39000, 480, 250, 0, airline="British Airways"),
    _Spec("4bb1c5", "AZA1234", "A320", 140, 25, 4200, 220, 95, -1100, airline="ITA Airways"),
    _Spec("a1b2c3", "RYR7BX", "B738", 200, 55, 37000, 450, 340, 0, airline="Ryanair"),
    _Spec("39a840", "EZY82CD", "A21N", 290, 60, 22000, 380, 60, 1800, airline="easyJet"),
    _Spec("4baa11", "VLG1122", "A320", 15, 88, 36000, 440, 190, 0, airline="Vueling"),
    _Spec("aa5588", "N823CS", "GLF5", 100, 18, 41000, 470, 30, 0, airline="Privatjet"),
    _Spec("47c2de", "SWR44X", "BCS3", 250, 45, 35000, 420, 275, 500, airline="Swiss"),
    _Spec("3d2c1b", "DTA402", "AT76", 170, 15, 9500, 240, 150, -400, airline="Air Dolomiti"),
    _Spec("aabb01", "I-HELI", "A109", 330, 8, 1200, 95, 220, 0, airline="Rettungsflug"),
    _Spec("cc7711", "D-ECBA", "C172", 55, 12, 3200, 110, 80, 0),
    _Spec("112233", "TOPCAT11", "F16", 310, 30, 28000, 480, 130, 2500, squawk="1200",
          registered_owner="Aeronautica Militare"),
    _Spec("ff0011", "AUA7700", "A320", 175, 22, 11000, 260, 300, -2200, squawk="7700",
          airline="Austrian"),
    _Spec("990022", "WZZ3300", "A21N", 230, 68, 38000, 460, 85, 0, airline="Wizz Air"),
)

# Hauptflug für Flugdetail- und Tracking-Screenshots: DLH420,
# Frankfurt (FRA) -> Rom Fiumicino (FCO), auf 62% der Strecke -- ein Punkt,
# an dem Fortschrittsbalken/ETA/Reststrecke im Screenshot nicht trivial
# 0%/100% sind (route_progress.py klemmt zwar auf [0,100], aber ein
# Randwert wäre ein schlechtes Beispielbild).
_FRA = (50.0333, 8.5706)
_FCO = (41.8003, 12.2389)
_FRAC = 0.62


def _tracked_flight() -> Aircraft:
    lat = _FRA[0] + (_FCO[0] - _FRA[0]) * _FRAC
    lon = _FRA[1] + (_FCO[1] - _FRA[1]) * _FRAC
    return Aircraft(
        icao_hex="3c5ee1",
        callsign="DLH420",
        registration="D-AIUZ",
        aircraft_type="A320",
        lat=lat,
        lon=lon,
        altitude_ft=37000,
        ground_speed_kt=445.0,
        track_deg=138.0,
        vertical_rate_fpm=0,
        squawk="1000",
        airline="Lufthansa",
        origin="FRA",
        destination="FCO",
        origin_lat=_FRA[0],
        origin_lon=_FRA[1],
        destination_lat=_FCO[0],
        destination_lon=_FCO[1],
        registered_owner="Lufthansa",
        photo_credit="",
    )


def build_aircraft() -> list[Aircraft]:
    """Die vierzehn allgemeinen Flugzeuge für den Radar-Screenshot."""
    out: list[Aircraft] = []
    for s in _SPECS:
        lat, lon = _offset(s.bearing, s.dist_km)
        out.append(
            Aircraft(
                icao_hex=s.hex_id,
                callsign=s.callsign,
                aircraft_type=s.ac_type,
                lat=lat,
                lon=lon,
                altitude_ft=s.alt_ft,
                ground_speed_kt=s.speed_kt,
                track_deg=s.heading,
                vertical_rate_fpm=s.vs_fpm,
                squawk=s.squawk,
                distance_km=s.dist_km,
                bearing_deg=s.bearing,
                airline=s.airline,
                registered_owner=s.registered_owner,
            )
        )
    return out


def build_tracked_flight() -> Aircraft:
    return _tracked_flight()


def build_weather() -> WeatherData:
    return WeatherData(
        temperature_c=21.0,
        humidity=52.0,
        wind_speed_ms=12.0 / 3.6,
        wind_direction_deg=210.0,
        weather_code=1100,
        condition="Überwiegend klar",
        temperature_apparent_c=20.0,
        precipitation_probability_pct=5.0,
    )


def build_forecast() -> list[DailyForecast]:
    codes_conditions = (
        ("2026-08-27", 15.0, 24.0, 1000, "Klar"),
        ("2026-08-28", 16.0, 25.0, 1100, "Überwiegend klar"),
        ("2026-08-29", 14.0, 21.0, 4200, "Regenschauer"),
        ("2026-08-30", 13.0, 20.0, 1101, "Teilweise bewölkt"),
        ("2026-08-31", 15.0, 23.0, 1000, "Klar"),
    )
    return [
        DailyForecast(date=d, temp_min_c=lo, temp_max_c=hi, weather_code=code, condition=cond)
        for d, lo, hi, code, cond in codes_conditions
    ]


@contextmanager
def frozen_time():
    """Hält `time.time()`/`time.monotonic()` für reproduzierbare Sweep-
    Winkel und Alarm-Blinkphasen fest, solange der Context aktiv ist.

    `renderer.py` liest beide Uhren direkt (Wanduhrzeit für den
    Sweep-Winkel, Monotonic für Ein-/Ausblend-Animationen) -- ohne das hier
    würde jeder Buildlauf ein anderes Sweep-Bild erzeugen.
    """
    import time as _time

    real_time = _time.time
    real_monotonic = _time.monotonic
    _time.time = lambda: FROZEN_MONOTONIC
    _time.monotonic = lambda: FROZEN_MONOTONIC
    try:
        yield
    finally:
        _time.time = real_time
        _time.monotonic = real_monotonic


def location_label() -> str:
    return HOME.label


__all__ = [
    "HOME",
    "HOME_LAT",
    "HOME_LON",
    "LOCATIONS",
    "build_aircraft",
    "build_tracked_flight",
    "build_weather",
    "build_forecast",
    "frozen_time",
    "location_label",
]

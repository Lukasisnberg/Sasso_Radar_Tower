"""Data models for aircraft and flight information."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Aircraft:
    icao_hex: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    altitude_ft: Optional[int] = None
    ground_speed_kt: Optional[float] = None
    track_deg: Optional[float] = None
    vertical_rate_fpm: Optional[int] = None
    squawk: Optional[str] = None
    callsign: Optional[str] = None
    registration: Optional[str] = None
    aircraft_type: Optional[str] = None
    is_on_ground: bool = False
    last_seen_s: float = 0.0
    distance_km: Optional[float] = None
    bearing_deg: Optional[float] = None
    category: Optional[str] = None
    # enriched fields (from FR24 / AirLabs / adsbdb)
    airline: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    flight_number: Optional[str] = None
    registered_owner: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    # photo fields (populated by aircraft_photo background thread)
    photo_path: Optional[str] = None
    photo_credit: Optional[str] = None
    # branding fields
    operator_icao: Optional[str] = None
    airline_icao: Optional[str] = None

    @property
    def is_emergency(self) -> bool:
        return self.squawk in ("7500", "7600", "7700")

    @property
    def is_military(self) -> bool:
        if self.squawk and self.squawk.startswith("7"):
            return False
        cat = (self.category or "").upper()
        if cat in ("A6", "A7", "B6", "B7"):
            return True
        cs = (self.callsign or "").upper()
        mil_prefixes = (
            "RCH", "NAVY", "ARMY", "DUKE", "COBRA", "TOPCAT", "EVAC",
            "REACH", "FORGE", "VALOR", "HAWK", "VIPER", "SKULL",
        )
        return any(cs.startswith(p) for p in mil_prefixes)

    @property
    def display_label(self) -> str:
        return self.callsign or self.registration or self.icao_hex

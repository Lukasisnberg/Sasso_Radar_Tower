"""Demo data source — generates simulated aircraft for testing without network."""

import math
import random
import time
from typing import Optional

from flugradar.config.settings import HomeLocation
from flugradar.data_sources.geo import haversine_km, bearing_deg
from flugradar.data_sources.models import Aircraft

_CALLSIGNS = [
    "SWR", "DLH", "BAW", "AFR", "KLM", "UAE", "SIA",
    "AAL", "UAL", "DAL", "RYR", "EZY", "WZZ", "THY",
]
_TYPES = ["A320", "B738", "A321", "B77W", "A333", "E190", "B789", "A359"]


class DemoSource:
    """Generates realistic-looking simulated traffic around home."""

    def __init__(self, home: HomeLocation, count: int = 30) -> None:
        self._home = home
        self._aircraft: list[_SimAircraft] = []
        self._spawn_time = time.monotonic()
        for _ in range(count):
            self._aircraft.append(self._new_aircraft())

    def get_aircraft(self, force_refresh: bool = False) -> list[Aircraft]:
        dt = 1.0 / 30
        results: list[Aircraft] = []
        for sim in self._aircraft:
            sim.step(dt)
            dist = haversine_km(self._home.lat, self._home.lon, sim.lat, sim.lon)
            if dist > self._home.radius_km * 1.5:
                idx = self._aircraft.index(sim)
                self._aircraft[idx] = self._new_aircraft()
                sim = self._aircraft[idx]
                dist = haversine_km(self._home.lat, self._home.lon, sim.lat, sim.lon)

            brng = bearing_deg(self._home.lat, self._home.lon, sim.lat, sim.lon)
            ac = Aircraft(
                icao_hex=sim.hex_id,
                lat=sim.lat,
                lon=sim.lon,
                altitude_ft=sim.alt_ft,
                ground_speed_kt=sim.speed_kt,
                track_deg=sim.heading,
                vertical_rate_fpm=sim.vs,
                squawk=sim.squawk,
                callsign=sim.callsign,
                aircraft_type=sim.ac_type,
                distance_km=dist,
                bearing_deg=brng,
            )
            results.append(ac)
        results.sort(key=lambda a: a.distance_km or 0)
        return results

    def _new_aircraft(self) -> "_SimAircraft":
        angle = random.uniform(0, 360)
        dist_km = random.uniform(10, self._home.radius_km * 0.9)
        lat = self._home.lat + (dist_km / 111.32) * math.cos(math.radians(angle))
        cos_home = math.cos(math.radians(self._home.lat))
        lon = self._home.lon + (dist_km / (111.32 * cos_home)) * math.sin(math.radians(angle))
        heading = random.uniform(0, 360)
        alt = random.choice([3000, 6000, 10000, 18000, 25000, 33000, 36000, 39000, 41000])
        speed = 150 + alt / 100
        prefix = random.choice(_CALLSIGNS)
        num = random.randint(100, 9999)
        hex_id = f"{random.randint(0x100000, 0xffffff):06x}"
        squawk = "7700" if random.random() < 0.02 else f"{random.randint(1000, 7677):04d}"
        return _SimAircraft(
            hex_id=hex_id,
            callsign=f"{prefix}{num}",
            ac_type=random.choice(_TYPES),
            lat=lat,
            lon=lon,
            alt_ft=alt,
            speed_kt=speed,
            heading=heading,
            vs=random.choice([0, 0, 0, 1500, -1200, 2000, -800]),
            squawk=squawk,
        )

    def close(self) -> None:
        pass


class _SimAircraft:
    def __init__(self, **kwargs):
        self.hex_id: str = kwargs["hex_id"]
        self.callsign: str = kwargs["callsign"]
        self.ac_type: str = kwargs["ac_type"]
        self.lat: float = kwargs["lat"]
        self.lon: float = kwargs["lon"]
        self.alt_ft: int = kwargs["alt_ft"]
        self.speed_kt: float = kwargs["speed_kt"]
        self.heading: float = kwargs["heading"]
        self.vs: int = kwargs["vs"]
        self.squawk: str = kwargs["squawk"]

    def step(self, dt: float) -> None:
        speed_kmh = self.speed_kt * 1.852
        dist_km = speed_kmh * dt / 3600
        self.lat += (dist_km / 111.32) * math.cos(math.radians(self.heading))
        cos_lat = math.cos(math.radians(self.lat))
        if cos_lat > 0.01:
            self.lon += (dist_km / (111.32 * cos_lat)) * math.sin(math.radians(self.heading))
        self.heading = (self.heading + random.uniform(-0.3, 0.3)) % 360

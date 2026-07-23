"""Project geographic coordinates (lat/lon) to screen pixel positions.

Uses an equirectangular approximation centred on the home location,
which is accurate enough for the ~200 km radius we display.
"""

import math
from dataclasses import dataclass

from flugradar.data_sources.geo import EARTH_RADIUS_KM


@dataclass
class ScreenProjection:
    """Maps lat/lon to pixel coordinates on a square display centred on home."""

    home_lat: float
    home_lon: float
    radius_km: float
    screen_size: int  # pixels (width = height)

    @property
    def centre(self) -> tuple[float, float]:
        return self.screen_size / 2, self.screen_size / 2

    @property
    def pixels_per_km(self) -> float:
        return (self.screen_size / 2) / self.radius_km

    def geo_to_screen(self, lat: float, lon: float) -> tuple[float, float]:
        """Convert lat/lon to (x, y) pixel position. Origin is top-left."""
        dx_km = self._lon_diff_km(lon)
        dy_km = self._lat_diff_km(lat)
        cx, cy = self.centre
        x = cx + dx_km * self.pixels_per_km
        y = cy - dy_km * self.pixels_per_km  # screen y is inverted
        return x, y

    def screen_to_geo(self, x: float, y: float) -> tuple[float, float]:
        """Convert pixel (x, y) back to (lat, lon)."""
        cx, cy = self.centre
        dx_km = (x - cx) / self.pixels_per_km
        dy_km = (cy - y) / self.pixels_per_km
        lat = self.home_lat + math.degrees(dy_km / EARTH_RADIUS_KM)
        cos_lat = math.cos(math.radians(self.home_lat))
        lon = self.home_lon + math.degrees(dx_km / (EARTH_RADIUS_KM * cos_lat))
        return lat, lon

    def is_on_screen(self, x: float, y: float, margin: int = 20) -> bool:
        return (-margin <= x <= self.screen_size + margin and
                -margin <= y <= self.screen_size + margin)

    def distance_to_pixels(self, km: float) -> float:
        return km * self.pixels_per_km

    def _lat_diff_km(self, lat: float) -> float:
        return math.radians(lat - self.home_lat) * EARTH_RADIUS_KM

    def _lon_diff_km(self, lon: float) -> float:
        cos_lat = math.cos(math.radians(self.home_lat))
        return math.radians(lon - self.home_lon) * EARTH_RADIUS_KM * cos_lat

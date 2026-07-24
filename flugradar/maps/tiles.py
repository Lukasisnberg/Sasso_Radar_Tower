"""Slippy-map tile downloader with disk cache and colour post-processing.

Supports multiple tile providers (CARTO, OSM, FAA VFR).
Downloads are parallelised with a thread pool.
"""

import hashlib
import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

_TILE_SIZE = 256


@dataclass(frozen=True)
class TileProvider:
    name: str
    url_template: str
    attribution: str
    max_zoom: int = 18
    headers: dict[str, str] | None = None


PROVIDERS: dict[str, TileProvider] = {
    "carto_dark": TileProvider(
        name="CARTO Dark (no labels)",
        url_template="https://basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}@2x.png",
        attribution="© CARTO © OpenStreetMap contributors",
        max_zoom=18,
    ),
    "carto_light": TileProvider(
        name="CARTO Positron (no labels)",
        url_template="https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}@2x.png",
        attribution="© CARTO © OpenStreetMap contributors",
        max_zoom=18,
    ),
    "osm": TileProvider(
        name="OpenStreetMap",
        url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution="© OpenStreetMap contributors",
        max_zoom=19,
        headers={"User-Agent": "SassoRadarTower/0.1"},
    ),
    # Transparent aviation overlay (airspaces, airports, navaids, reporting
    # points), not a standalone basemap -- meant to be layered on top of
    # carto_dark/osm/etc. Requires a free openAIP account + API client key
    # (see https://www.openaip.net -> profile -> API Clients). Data is
    # licensed CC BY-NC 4.0 (non-commercial, attribution required) --
    # https://creativecommons.org/licenses/by-nc/4.0/. Verified against the
    # live Tiles API OpenAPI schema on 2026-07-24.
    "openaip": TileProvider(
        name="openAIP (aviation overlay)",
        url_template="https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.png?apiKey={api_key}",
        attribution="© openAIP (CC BY-NC 4.0)",
        max_zoom=14,
    ),
}


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lon to tile x/y at given zoom level."""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lat_lon(x: int, y: int, zoom: int) -> tuple[float, float]:
    """Convert tile x/y to lat/lon of top-left corner."""
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def zoom_for_radius(radius_km: float, lat: float, screen_size: int) -> int:
    """Pick a zoom level that fits the radius into the screen."""
    for z in range(18, 0, -1):
        metres_per_px = 156543.03 * math.cos(math.radians(lat)) / (2 ** z)
        km_per_px = metres_per_px / 1000.0
        visible_km = km_per_px * screen_size / 2
        if visible_km >= radius_km:
            return z
    return 1


class TileCache:
    """Disk-backed tile cache."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        if cache_dir is None:
            cache_dir = Path(os.environ.get(
                "FLUGRADAR_DATA_DIR",
                Path.home() / ".local" / "share" / "flugradar",
            )) / "tile_cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, provider: str, z: int, x: int, y: int) -> Path:
        return self.cache_dir / provider / str(z) / str(x) / f"{y}.png"

    def get(self, provider: str, z: int, x: int, y: int) -> Optional[bytes]:
        p = self._path(provider, z, x, y)
        if p.exists():
            return p.read_bytes()
        return None

    def put(self, provider: str, z: int, x: int, y: int, data: bytes) -> None:
        p = self._path(provider, z, x, y)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


class TileManager:
    """Downloads, caches, and composites map tiles."""

    def __init__(
        self,
        provider_key: str = "carto_dark",
        cache: Optional[TileCache] = None,
        max_workers: int = 4,
        api_key: str = "",
    ) -> None:
        self.provider = PROVIDERS[provider_key]
        self.provider_key = provider_key
        self._api_key = api_key
        self.cache = cache or TileCache()
        self._session = requests.Session()
        if self.provider.headers:
            self._session.headers.update(self.provider.headers)
        else:
            self._session.headers["User-Agent"] = "SassoRadarTower/0.1"
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    @property
    def attribution(self) -> str:
        return self.provider.attribution

    def fetch_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        cached = self.cache.get(self.provider_key, z, x, y)
        if cached:
            return cached
        url = self.provider.url_template.format(z=z, x=x, y=y, api_key=self._api_key)
        try:
            resp = self._session.get(url, timeout=10)
            if resp.status_code == 204:
                # Zoom level outside the provider's supported range (e.g.
                # openAIP's Tiles API). Not an error, just no tile here --
                # don't cache an empty response as if it were real data.
                return None
            resp.raise_for_status()
            data = resp.content
            self.cache.put(self.provider_key, z, x, y, data)
            return data
        except Exception:
            log.warning("Tile fetch failed: z=%d x=%d y=%d", z, x, y)
            return None

    def fetch_region(
        self,
        centre_lat: float,
        centre_lon: float,
        radius_km: float,
        screen_size: int,
    ) -> list[tuple[int, int, int, bytes]]:
        """Fetch all tiles covering the visible area. Returns (z, x, y, png_data)."""
        zoom = zoom_for_radius(radius_km, centre_lat, screen_size)
        zoom = min(zoom, self.provider.max_zoom)

        cx, cy = lat_lon_to_tile(centre_lat, centre_lon, zoom)

        n = 2 ** zoom
        metres_per_px = 156543.03 * math.cos(math.radians(centre_lat)) / n
        km_per_tile = metres_per_px * _TILE_SIZE / 1000.0
        tiles_needed = max(1, int(math.ceil(radius_km / km_per_tile)) + 1)

        coords = []
        for dx in range(-tiles_needed, tiles_needed + 1):
            for dy in range(-tiles_needed, tiles_needed + 1):
                tx = (cx + dx) % n
                ty = cy + dy
                if 0 <= ty < n:
                    coords.append((zoom, tx, ty))

        results: list[tuple[int, int, int, bytes]] = []
        futures = {
            self._pool.submit(self.fetch_tile, z, x, y): (z, x, y)
            for z, x, y in coords
        }
        for future in as_completed(futures):
            z, x, y = futures[future]
            data = future.result()
            if data:
                results.append((z, x, y, data))

        return results

    def close(self) -> None:
        self._pool.shutdown(wait=False)
        self._session.close()

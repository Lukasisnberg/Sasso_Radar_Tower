"""Composites map tiles onto a pygame surface with colour grading."""

import math
from io import BytesIO
from typing import Optional

import pygame

from flugradar.data_sources.projection import ScreenProjection
from flugradar.maps.tiles import TileManager, tile_to_lat_lon, zoom_for_radius, _TILE_SIZE


class MapCompositor:
    """Renders map tiles onto a pygame surface, aligned to the radar projection."""

    def __init__(
        self,
        tile_manager: TileManager,
        projection: ScreenProjection,
        brightness: float = 0.4,
        contrast: float = 0.8,
    ) -> None:
        self.tiles = tile_manager
        self.proj = projection
        self.brightness = brightness
        self.contrast = contrast
        self._cached_surface: Optional[pygame.Surface] = None
        self._cached_key: Optional[tuple] = None

    def render(self, target: pygame.Surface) -> None:
        cache_key = (
            round(self.proj.home_lat, 4),
            round(self.proj.home_lon, 4),
            round(self.proj.radius_km, 1),
            self.proj.screen_size,
        )
        if self._cached_key == cache_key and self._cached_surface is not None:
            target.blit(self._cached_surface, (0, 0))
            return

        size = self.proj.screen_size
        map_surf = pygame.Surface((size, size))
        map_surf.fill((10, 15, 10))

        tile_data = self.tiles.fetch_region(
            self.proj.home_lat, self.proj.home_lon,
            self.proj.radius_km, size,
        )

        for z, tx, ty, png_data in tile_data:
            try:
                tile_surf = pygame.image.load(BytesIO(png_data))
            except Exception:
                continue

            tile_lat, tile_lon = tile_to_lat_lon(tx, ty, z)
            sx, sy = self.proj.geo_to_screen(tile_lat, tile_lon)

            n = 2 ** z
            metres_per_px = 156543.03 * math.cos(math.radians(self.proj.home_lat)) / n
            km_per_tile_px = metres_per_px / 1000.0
            tile_screen_px = km_per_tile_px * self.proj.pixels_per_km

            tw = tile_surf.get_width()
            scale = tile_screen_px / (tw / _TILE_SIZE) if tw > 0 else 1.0
            scaled_size = max(1, int(tw * scale))
            tile_surf = pygame.transform.smoothscale(tile_surf, (scaled_size, scaled_size))

            self._colour_grade(tile_surf)
            map_surf.blit(tile_surf, (int(sx), int(sy)))

        self._cached_surface = map_surf
        self._cached_key = cache_key
        target.blit(map_surf, (0, 0))

    def invalidate(self) -> None:
        self._cached_surface = None
        self._cached_key = None

    def _colour_grade(self, surface: pygame.Surface) -> None:
        """Darken and desaturate tiles to match the radar aesthetic."""
        arr = pygame.surfarray.pixels3d(surface)
        arr_float = arr.astype(float)
        grey = arr_float.mean(axis=2, keepdims=True)
        arr_float = grey + (arr_float - grey) * self.contrast
        arr_float *= self.brightness
        arr_float.clip(0, 255, out=arr_float)
        arr[:] = arr_float.astype(arr.dtype)
        del arr

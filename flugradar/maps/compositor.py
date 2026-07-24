"""Composites map tiles onto a pygame surface with colour grading.

Supports an optional base layer (or none, for "no map") plus any number
of independently-togglable transparent overlays (openAIP, RainViewer).
Rebuilding the composited surface (base + overlays) happens on a
background thread: render() always blits whatever was last built
immediately and never blocks the caller, so switching providers/toggling
an overlay can never stall the sweep animation -- the old image just
keeps showing until the new one is ready.
"""

import math
import threading
from io import BytesIO
from typing import Optional

import pygame

from flugradar.data_sources.projection import ScreenProjection
from flugradar.maps.tiles import TileManager, tile_to_lat_lon, zoom_for_radius, _TILE_SIZE


class MapCompositor:
    """Renders map tiles onto a pygame surface, aligned to the radar projection."""

    def __init__(
        self,
        tile_manager: Optional[TileManager],
        projection: ScreenProjection,
        brightness: float = 0.4,
        contrast: float = 0.8,
        overlay_tiles: Optional[list[TileManager]] = None,
    ) -> None:
        self.tiles = tile_manager
        self.overlay_tiles: list[TileManager] = list(overlay_tiles or [])
        self.proj = projection
        self.brightness = brightness
        self.contrast = contrast
        self._lock = threading.Lock()
        self._cached_surface: Optional[pygame.Surface] = None
        self._cached_key: Optional[tuple] = None
        self._pending_key: Optional[tuple] = None
        self._generation = 0

    @property
    def attribution(self) -> str:
        parts = []
        if self.tiles is not None:
            parts.append(self.tiles.attribution)
        parts.extend(o.attribution for o in self.overlay_tiles)
        return " · ".join(parts)

    def render(self, target: pygame.Surface) -> None:
        with self._lock:
            cache_key = (
                round(self.proj.home_lat, 4),
                round(self.proj.home_lon, 4),
                round(self.proj.radius_km, 1),
                self.proj.screen_size,
                self._generation,
            )
            show_surface = self._cached_surface
            need_build = self._pending_key != cache_key
            if need_build:
                self._pending_key = cache_key

        if need_build:
            threading.Thread(target=self._build_surface, args=(cache_key,), daemon=True).start()

        if show_surface is not None:
            target.blit(show_surface, (0, 0))
        else:
            target.fill((10, 15, 10))

    def _build_surface(self, cache_key: tuple) -> None:
        size = self.proj.screen_size
        map_surf = pygame.Surface((size, size))
        map_surf.fill((10, 15, 10))

        if self.tiles is not None:
            tile_data = self.tiles.fetch_region(
                self.proj.home_lat, self.proj.home_lon,
                self.proj.radius_km, size,
            )
            for z, tx, ty, png_data in tile_data:
                self._blit_tile(map_surf, z, tx, ty, png_data, grade=True)

        for overlay in self.overlay_tiles:
            overlay_data = overlay.fetch_region(
                self.proj.home_lat, self.proj.home_lon,
                self.proj.radius_km, size,
            )
            for z, tx, ty, png_data in overlay_data:
                # Overlay symbology (airspace boundaries, rain intensity)
                # must stay legible/colour-accurate -- no dark-theme grading.
                self._blit_tile(map_surf, z, tx, ty, png_data, grade=False)

        with self._lock:
            if self._pending_key == cache_key:
                self._cached_surface = map_surf
                self._cached_key = cache_key

    def _blit_tile(
        self,
        map_surf: pygame.Surface,
        z: int, tx: int, ty: int,
        png_data: bytes,
        grade: bool,
    ) -> None:
        try:
            tile_surf = pygame.image.load(BytesIO(png_data)).convert_alpha()
        except Exception:
            return

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

        if grade:
            self._colour_grade(tile_surf)
        map_surf.blit(tile_surf, (int(sx), int(sy)))

    def invalidate(self) -> None:
        """Force a rebuild on the next render() call.

        Does *not* clear the currently-shown surface -- render() keeps
        blitting the old one (better than a blank frame) until the
        background rebuild finishes.
        """
        with self._lock:
            self._generation += 1

    def _colour_grade(self, surface: pygame.Surface) -> None:
        """Darken and desaturate tiles to match the radar aesthetic."""
        try:
            arr = pygame.surfarray.pixels3d(surface)
        except Exception:
            surface.fill(
                (int(10 * self.brightness), int(15 * self.brightness), int(10 * self.brightness))
            )
            return
        arr_float = arr.astype(float)
        grey = arr_float.mean(axis=2, keepdims=True)
        arr_float = grey + (arr_float - grey) * self.contrast
        arr_float *= self.brightness
        arr_float.clip(0, 255, out=arr_float)
        arr[:] = arr_float.astype(arr.dtype)
        del arr

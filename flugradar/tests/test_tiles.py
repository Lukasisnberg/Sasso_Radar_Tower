"""Unit tests for tile coordinate math, caching, and compositing."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pygame
import pytest

from flugradar.maps.tiles import (
    lat_lon_to_tile,
    tile_to_lat_lon,
    zoom_for_radius,
    PROVIDERS,
    TileCache,
    TileManager,
)


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    yield
    pygame.quit()


class TestTileCoords:
    def test_origin(self):
        x, y = lat_lon_to_tile(0, 0, 1)
        assert x == 1
        assert y == 1

    def test_zurich_z10(self):
        x, y = lat_lon_to_tile(47.3769, 8.5417, 10)
        assert 530 <= x <= 540
        assert 355 <= y <= 365

    def test_roundtrip_approx(self):
        z = 12
        x, y = lat_lon_to_tile(47.3769, 8.5417, z)
        lat, lon = tile_to_lat_lon(x, y, z)
        assert lat == pytest.approx(47.3769, abs=0.1)
        assert lon == pytest.approx(8.5417, abs=0.1)


class TestZoomForRadius:
    def test_small_radius(self):
        z = zoom_for_radius(10, 47.0, 720)
        assert z >= 10

    def test_large_radius(self):
        z = zoom_for_radius(400, 47.0, 720)
        assert z <= 8

    def test_monotonic(self):
        z_small = zoom_for_radius(20, 47.0, 720)
        z_large = zoom_for_radius(200, 47.0, 720)
        assert z_small >= z_large


class TestTileCache:
    def test_miss_returns_none(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        assert cache.get("carto_dark", 10, 100, 200) is None

    def test_put_and_get(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        data = b"\x89PNG fake tile data"
        cache.put("carto_dark", 10, 100, 200, data)
        assert cache.get("carto_dark", 10, 100, 200) == data

    def test_different_providers(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        cache.put("carto_dark", 10, 100, 200, b"dark")
        cache.put("osm", 10, 100, 200, b"osm")
        assert cache.get("carto_dark", 10, 100, 200) == b"dark"
        assert cache.get("osm", 10, 100, 200) == b"osm"

    def test_openaip_does_not_mix_with_base_providers(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        cache.put("carto_dark", 10, 100, 200, b"dark")
        cache.put("osm", 10, 100, 200, b"osm")
        cache.put("openaip", 10, 100, 200, b"openaip-overlay")
        assert cache.get("carto_dark", 10, 100, 200) == b"dark"
        assert cache.get("osm", 10, 100, 200) == b"osm"
        assert cache.get("openaip", 10, 100, 200) == b"openaip-overlay"


class TestOpenAipProvider:
    def test_provider_entry_exists(self):
        assert "openaip" in PROVIDERS
        assert "{api_key}" in PROVIDERS["openaip"].url_template

    def test_api_key_substituted_into_url(self, tmp_path):
        tm = TileManager(
            provider_key="openaip", api_key="secret123",
            cache=TileCache(tmp_path / "tiles"),
        )
        with patch.object(tm, "_session") as mock_session:
            resp = MagicMock(status_code=200, content=b"png-bytes")
            resp.raise_for_status = MagicMock()
            mock_session.get.return_value = resp
            tm.fetch_tile(8, 1, 1)

        called_url = mock_session.get.call_args[0][0]
        assert "apiKey=secret123" in called_url
        tm.close()

    def test_no_key_still_makes_a_request_without_crashing(self, tmp_path):
        """Verified live: a missing/invalid key returns HTTP 403/404, not a
        crash. fetch_tile must handle that gracefully (returns None)."""
        tm = TileManager(
            provider_key="openaip", api_key="",
            cache=TileCache(tmp_path / "tiles"),
        )
        with patch.object(tm, "_session") as mock_session:
            import requests
            resp = MagicMock(status_code=403)
            resp.raise_for_status.side_effect = requests.HTTPError("403")
            mock_session.get.return_value = resp
            result = tm.fetch_tile(8, 1, 1)

        assert result is None
        tm.close()

    def test_204_out_of_zoom_range_is_not_cached_as_a_tile(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        tm = TileManager(provider_key="openaip", api_key="k", cache=cache)
        with patch.object(tm, "_session") as mock_session:
            resp = MagicMock(status_code=204)
            mock_session.get.return_value = resp
            result = tm.fetch_tile(1, 0, 0)

        assert result is None
        assert cache.get("openaip", 1, 0, 0) is None
        tm.close()


class TestCompositorSmoothscale:
    """Ensure tiles with unusual pixel formats don't crash smoothscale."""

    def test_palette_mode_tile_does_not_crash(self):
        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor
        from flugradar.maps.tiles import TileManager

        proj = ScreenProjection(
            home_lat=47.3769, home_lon=8.5417,
            radius_km=50.0, screen_size=200,
        )

        palette_surf = pygame.Surface((256, 256), depth=8)
        palette_surf.set_palette([(i, i, i) for i in range(256)])
        palette_surf.fill(42)
        buf = BytesIO()
        pygame.image.save(palette_surf, buf, "BMP")
        tile_bytes = buf.getvalue()

        tile_mgr = TileManager(provider_key="carto_dark")
        fake_tiles = [(10, 536, 360, tile_bytes)]
        with patch.object(tile_mgr, "fetch_region", return_value=fake_tiles):
            compositor = MapCompositor(tile_mgr, proj)
            target = pygame.Surface((200, 200))
            compositor.render(target)


class TestOverlayCompositing:
    def _make_png_tile_bytes(self) -> bytes:
        surf = pygame.Surface((256, 256), pygame.SRCALPHA)
        surf.fill((255, 0, 0, 128))
        buf = BytesIO()
        pygame.image.save(surf, buf, "PNG")
        return buf.getvalue()

    def test_renders_with_overlay_without_crashing(self):
        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor

        proj = ScreenProjection(home_lat=47.3769, home_lon=8.5417, radius_km=50.0, screen_size=200)
        tile_bytes = self._make_png_tile_bytes()
        fake_tiles = [(10, 536, 360, tile_bytes)]

        base = TileManager(provider_key="carto_dark")
        overlay = TileManager(provider_key="openaip", api_key="k")
        with patch.object(base, "fetch_region", return_value=fake_tiles), \
             patch.object(overlay, "fetch_region", return_value=fake_tiles):
            compositor = MapCompositor(base, proj, overlay_tiles=overlay)
            target = pygame.Surface((200, 200))
            compositor.render(target)  # must not raise

    def test_attribution_combines_base_and_overlay(self):
        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor

        proj = ScreenProjection(home_lat=47.3769, home_lon=8.5417, radius_km=50.0, screen_size=200)
        base = TileManager(provider_key="carto_dark")
        compositor_no_overlay = MapCompositor(base, proj)
        assert "openAIP" not in compositor_no_overlay.attribution

        overlay = TileManager(provider_key="openaip", api_key="k")
        compositor_with_overlay = MapCompositor(base, proj, overlay_tiles=overlay)
        assert "openAIP" in compositor_with_overlay.attribution
        assert "CARTO" in compositor_with_overlay.attribution

    def test_no_overlay_does_not_fetch_overlay_tiles(self):
        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor

        proj = ScreenProjection(home_lat=47.3769, home_lon=8.5417, radius_km=50.0, screen_size=200)
        base = TileManager(provider_key="carto_dark")
        with patch.object(base, "fetch_region", return_value=[]):
            compositor = MapCompositor(base, proj)  # overlay_tiles=None
            target = pygame.Surface((200, 200))
            compositor.render(target)
        assert compositor.overlay_tiles is None

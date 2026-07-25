"""Unit tests for tile coordinate math, caching, and compositing."""

import time
from io import BytesIO
from unittest.mock import MagicMock, patch

import pygame
import pytest

from flugradar.maps.tiles import (
    lat_lon_to_tile,
    tile_to_lat_lon,
    zoom_for_radius,
    resolve_provider_key,
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


def _wait_for(predicate, timeout=2.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


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


class TestTileCacheEviction:
    """Unlike the aircraft-photo cache, tiles had no disk-size cap at all
    before this -- every provider/zoom/location ever viewed just piled up
    on disk forever."""

    def test_under_budget_evicts_nothing(self, monkeypatch, tmp_path):
        import flugradar.maps.tiles as tiles_mod
        monkeypatch.setattr(tiles_mod, "_MAX_CACHE_BYTES", 10_000)
        cache = TileCache(tmp_path / "tiles")
        cache.put("carto_dark", 10, 100, 200, b"x" * 100)

        cache.evict_if_needed()

        assert cache.get("carto_dark", 10, 100, 200) == b"x" * 100

    def test_evicts_oldest_first_when_over_budget(self, monkeypatch, tmp_path):
        import os
        import flugradar.maps.tiles as tiles_mod
        monkeypatch.setattr(tiles_mod, "_MAX_CACHE_BYTES", 1500)
        cache = TileCache(tmp_path / "tiles")

        # Three 1000-byte tiles, written oldest-first with distinct mtimes.
        for i, y in enumerate([100, 200, 300]):
            cache.put("carto_dark", 10, i, y, b"x" * 1000)
            path = cache._path("carto_dark", 10, i, y)
            os.utime(path, (1000.0 + i, 1000.0 + i))

        cache.evict_if_needed()

        assert cache.get("carto_dark", 10, 0, 100) is None  # oldest evicted
        assert cache.get("carto_dark", 10, 2, 300) is not None  # newest kept

    def test_evicts_across_providers_by_age_not_provider(self, monkeypatch, tmp_path):
        import os
        import flugradar.maps.tiles as tiles_mod
        monkeypatch.setattr(tiles_mod, "_MAX_CACHE_BYTES", 1000)
        cache = TileCache(tmp_path / "tiles")

        cache.put("carto_dark", 10, 1, 1, b"x" * 1000)
        os.utime(cache._path("carto_dark", 10, 1, 1), (1000.0, 1000.0))
        cache.put("osm", 10, 1, 1, b"x" * 1000)
        os.utime(cache._path("osm", 10, 1, 1), (2000.0, 2000.0))

        cache.evict_if_needed()

        assert cache.get("carto_dark", 10, 1, 1) is None
        assert cache.get("osm", 10, 1, 1) is not None

    def test_fetch_region_triggers_eviction_check(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        tm = TileManager(provider_key="carto_dark", cache=cache)
        mock_resp = MagicMock(status_code=200, content=b"tiledata")
        mock_resp.raise_for_status = MagicMock()

        with patch.object(tm._session, "get", return_value=mock_resp), \
             patch.object(cache, "evict_if_needed") as mock_evict:
            tm.fetch_region(47.0, 8.0, 50.0, 300)

        mock_evict.assert_called_once()
        tm.close()


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
            assert _wait_for(lambda: compositor._cached_key is not None)


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
            compositor = MapCompositor(base, proj, overlay_tiles=[overlay])
            target = pygame.Surface((200, 200))
            compositor.render(target)  # must not raise
            assert _wait_for(lambda: compositor._cached_key is not None)

    def test_multiple_overlays_active_simultaneously(self):
        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor

        proj = ScreenProjection(home_lat=47.3769, home_lon=8.5417, radius_km=50.0, screen_size=200)
        tile_bytes = self._make_png_tile_bytes()
        fake_tiles = [(10, 536, 360, tile_bytes)]

        base = TileManager(provider_key="carto_dark")
        openaip = TileManager(provider_key="openaip", api_key="k")
        rainviewer = TileManager(provider_key="rainviewer", frame_path_provider=lambda: "")
        with patch.object(base, "fetch_region", return_value=fake_tiles), \
             patch.object(openaip, "fetch_region", return_value=fake_tiles), \
             patch.object(rainviewer, "fetch_region", return_value=fake_tiles):
            compositor = MapCompositor(base, proj, overlay_tiles=[openaip, rainviewer])
            assert len(compositor.overlay_tiles) == 2
            target = pygame.Surface((200, 200))
            compositor.render(target)
            assert _wait_for(lambda: compositor._cached_key is not None)
            assert "openAIP" in compositor.attribution
            assert "RainViewer" in compositor.attribution

    def test_attribution_combines_base_and_overlay(self):
        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor

        proj = ScreenProjection(home_lat=47.3769, home_lon=8.5417, radius_km=50.0, screen_size=200)
        base = TileManager(provider_key="carto_dark")
        compositor_no_overlay = MapCompositor(base, proj)
        assert "openAIP" not in compositor_no_overlay.attribution

        overlay = TileManager(provider_key="openaip", api_key="k")
        compositor_with_overlay = MapCompositor(base, proj, overlay_tiles=[overlay])
        assert "openAIP" in compositor_with_overlay.attribution
        assert "CARTO" in compositor_with_overlay.attribution

    def test_no_overlay_does_not_fetch_overlay_tiles(self):
        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor

        proj = ScreenProjection(home_lat=47.3769, home_lon=8.5417, radius_km=50.0, screen_size=200)
        base = TileManager(provider_key="carto_dark")
        with patch.object(base, "fetch_region", return_value=[]):
            compositor = MapCompositor(base, proj)  # overlay_tiles defaults to []
            target = pygame.Surface((200, 200))
            compositor.render(target)
            assert _wait_for(lambda: compositor._cached_key is not None)
        assert compositor.overlay_tiles == []

    def test_no_base_map_only_overlay(self):
        """map_provider == 'none': tiles is None, only overlays render."""
        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor

        proj = ScreenProjection(home_lat=47.3769, home_lon=8.5417, radius_km=50.0, screen_size=200)
        overlay = TileManager(provider_key="openaip", api_key="k")
        with patch.object(overlay, "fetch_region", return_value=[]):
            compositor = MapCompositor(None, proj, overlay_tiles=[overlay])
            assert compositor.attribution == "© openAIP (CC BY-NC 4.0)"
            target = pygame.Surface((200, 200))
            compositor.render(target)  # must not raise despite tiles=None
            assert _wait_for(lambda: compositor._cached_key is not None)

    def test_render_does_not_block_on_slow_fetch(self):
        """A provider switch (or first-ever build) must not stall the
        caller -- render() returns immediately even while a slow tile
        fetch is still in flight on the background thread."""
        import threading

        from flugradar.data_sources.projection import ScreenProjection
        from flugradar.maps.compositor import MapCompositor

        proj = ScreenProjection(home_lat=47.3769, home_lon=8.5417, radius_km=50.0, screen_size=200)
        base = TileManager(provider_key="carto_dark")
        release = threading.Event()

        def slow_fetch_region(*args, **kwargs):
            release.wait(timeout=2.0)
            return []

        with patch.object(base, "fetch_region", side_effect=slow_fetch_region):
            compositor = MapCompositor(base, proj)
            target = pygame.Surface((200, 200))
            start = time.monotonic()
            compositor.render(target)
            elapsed = time.monotonic() - start
            assert elapsed < 0.5  # returned long before the fetch unblocks
            release.set()  # let the background thread finish so it doesn't linger


class TestResolveProviderKey:
    def test_known_base_providers_pass_through(self):
        assert resolve_provider_key("carto_dark") == "carto_dark"
        assert resolve_provider_key("carto_light") == "carto_light"
        assert resolve_provider_key("osm") == "osm"

    def test_none_sentinel_passes_through(self):
        assert resolve_provider_key("none") == "none"

    def test_unknown_falls_back_to_carto_dark(self):
        assert resolve_provider_key("bogus") == "carto_dark"
        assert resolve_provider_key("") == "carto_dark"

    def test_overlay_only_keys_are_not_valid_base_providers(self):
        assert resolve_provider_key("openaip") == "carto_dark"
        assert resolve_provider_key("rainviewer") == "carto_dark"


class TestRainViewerProvider:
    def test_provider_entry_exists(self):
        assert "rainviewer" in PROVIDERS
        assert "{frame_path}" in PROVIDERS["rainviewer"].url_template

    def test_frame_path_substituted_into_url(self, tmp_path):
        tm = TileManager(
            provider_key="rainviewer",
            cache=TileCache(tmp_path / "tiles"),
            frame_path_provider=lambda: "https://tilecache.rainviewer.com/v2/radar/abc123",
        )
        with patch.object(tm, "_session") as mock_session:
            resp = MagicMock(status_code=200, content=b"png-bytes")
            resp.raise_for_status = MagicMock()
            mock_session.get.return_value = resp
            tm.fetch_tile(6, 1, 1)

        called_url = mock_session.get.call_args[0][0]
        assert called_url.startswith("https://tilecache.rainviewer.com/v2/radar/abc123/256/6/1/1/")
        tm.close()

    def test_frame_change_clears_old_cache(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        frames = ["https://x/v2/radar/frame1"]
        tm = TileManager(
            provider_key="rainviewer", cache=cache,
            frame_path_provider=lambda: frames[0],
        )
        with patch.object(tm, "_session") as mock_session:
            resp = MagicMock(status_code=200, content=b"tile-a")
            resp.raise_for_status = MagicMock()
            mock_session.get.return_value = resp
            tm.fetch_tile(6, 1, 1)

        assert cache.get("rainviewer", 6, 1, 1) == b"tile-a"

        frames[0] = "https://x/v2/radar/frame2"  # simulate a new radar frame
        with patch.object(tm, "_session") as mock_session:
            resp = MagicMock(status_code=200, content=b"tile-b")
            resp.raise_for_status = MagicMock()
            mock_session.get.return_value = resp
            tm.fetch_tile(6, 1, 1)

        assert cache.get("rainviewer", 6, 1, 1) == b"tile-b"  # not the stale frame-1 tile
        tm.close()

    def test_no_frame_path_provider_leaves_placeholder_empty(self, tmp_path):
        tm = TileManager(provider_key="rainviewer", cache=TileCache(tmp_path / "tiles"))
        assert tm._resolve_frame_path() == ""
        tm.close()


class TestTileCacheClearProvider:
    def test_clears_only_the_named_provider(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        cache.put("rainviewer", 6, 1, 1, b"rain")
        cache.put("carto_dark", 6, 1, 1, b"dark")

        cache.clear_provider("rainviewer")

        assert cache.get("rainviewer", 6, 1, 1) is None
        assert cache.get("carto_dark", 6, 1, 1) == b"dark"

    def test_clearing_nonexistent_provider_does_not_raise(self, tmp_path):
        cache = TileCache(tmp_path / "tiles")
        cache.clear_provider("never_used")  # must not raise

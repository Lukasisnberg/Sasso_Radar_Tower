"""Unit tests for tile coordinate math and caching."""

import pytest

from flugradar.maps.tiles import (
    lat_lon_to_tile,
    tile_to_lat_lon,
    zoom_for_radius,
    TileCache,
)


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

"""Unit tests for the geo-to-screen projection."""

import math
import pytest

from flugradar.data_sources.projection import ScreenProjection


@pytest.fixture
def proj():
    return ScreenProjection(
        home_lat=47.3769,
        home_lon=8.5417,
        radius_km=100.0,
        screen_size=720,
    )


class TestGeoToScreen:
    def test_home_maps_to_centre(self, proj):
        x, y = proj.geo_to_screen(47.3769, 8.5417)
        assert x == pytest.approx(360.0)
        assert y == pytest.approx(360.0)

    def test_north_is_up(self, proj):
        _, y_north = proj.geo_to_screen(48.0, 8.5417)
        _, y_home = proj.geo_to_screen(47.3769, 8.5417)
        assert y_north < y_home  # screen y decreases going north

    def test_east_is_right(self, proj):
        x_east, _ = proj.geo_to_screen(47.3769, 9.0)
        x_home, _ = proj.geo_to_screen(47.3769, 8.5417)
        assert x_east > x_home

    def test_symmetry_north_south(self, proj):
        _, y_n = proj.geo_to_screen(47.3769 + 0.5, 8.5417)
        _, y_s = proj.geo_to_screen(47.3769 - 0.5, 8.5417)
        cy = 360.0
        assert (cy - y_n) == pytest.approx(y_s - cy, abs=0.1)

    def test_edge_at_radius(self, proj):
        km_per_deg_lat = 111.32
        delta_deg = 100.0 / km_per_deg_lat
        _, y = proj.geo_to_screen(47.3769 + delta_deg, 8.5417)
        assert y == pytest.approx(0.0, abs=2.0)


class TestScreenToGeo:
    def test_roundtrip(self, proj):
        lat_in, lon_in = 47.5, 8.7
        x, y = proj.geo_to_screen(lat_in, lon_in)
        lat_out, lon_out = proj.screen_to_geo(x, y)
        assert lat_out == pytest.approx(lat_in, abs=0.001)
        assert lon_out == pytest.approx(lon_in, abs=0.001)

    def test_centre_roundtrip(self, proj):
        lat, lon = proj.screen_to_geo(360, 360)
        assert lat == pytest.approx(47.3769, abs=0.0001)
        assert lon == pytest.approx(8.5417, abs=0.0001)


class TestIsOnScreen:
    def test_centre(self, proj):
        assert proj.is_on_screen(360, 360)

    def test_just_outside(self, proj):
        assert not proj.is_on_screen(-25, 360)
        assert not proj.is_on_screen(360, 745)

    def test_margin(self, proj):
        assert proj.is_on_screen(-15, 360, margin=20)


class TestDistanceToPixels:
    def test_full_radius(self, proj):
        px = proj.distance_to_pixels(100.0)
        assert px == pytest.approx(360.0)

    def test_half_radius(self, proj):
        px = proj.distance_to_pixels(50.0)
        assert px == pytest.approx(180.0)

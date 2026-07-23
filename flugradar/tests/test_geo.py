"""Unit tests for geographic utility functions."""

import math
import pytest
from flugradar.data_sources.geo import bearing_deg, haversine_km, km_to_unit


class TestHaversine:
    def test_same_point(self):
        assert haversine_km(47.0, 8.0, 47.0, 8.0) == 0.0

    def test_zurich_to_bern(self):
        dist = haversine_km(47.3769, 8.5417, 46.9480, 7.4474)
        assert 95 < dist < 105  # ~100 km

    def test_london_to_paris(self):
        dist = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
        assert 330 < dist < 350  # ~340 km

    def test_symmetry(self):
        d1 = haversine_km(47.0, 8.0, 48.0, 9.0)
        d2 = haversine_km(48.0, 9.0, 47.0, 8.0)
        assert d1 == pytest.approx(d2)


class TestBearing:
    def test_due_north(self):
        b = bearing_deg(47.0, 8.0, 48.0, 8.0)
        assert b == pytest.approx(0.0, abs=1.0)

    def test_due_east(self):
        b = bearing_deg(0.0, 0.0, 0.0, 1.0)
        assert b == pytest.approx(90.0, abs=0.1)

    def test_due_south(self):
        b = bearing_deg(48.0, 8.0, 47.0, 8.0)
        assert b == pytest.approx(180.0, abs=1.0)

    def test_due_west(self):
        b = bearing_deg(0.0, 1.0, 0.0, 0.0)
        assert b == pytest.approx(270.0, abs=0.1)


class TestUnitConversion:
    def test_km_identity(self):
        assert km_to_unit(100.0, "km") == 100.0

    def test_statute_miles(self):
        assert km_to_unit(100.0, "sm") == pytest.approx(62.137, abs=0.1)

    def test_nautical_miles(self):
        assert km_to_unit(100.0, "nm") == pytest.approx(53.996, abs=0.1)

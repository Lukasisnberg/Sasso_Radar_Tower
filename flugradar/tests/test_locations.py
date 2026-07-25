"""Tests for the fixed home-location presets and their display helpers."""

from flugradar.config.locations import (
    current_location_key,
    location_display_name,
    resolve_location,
)


class TestCurrentLocationKey:
    def test_matches_giessen(self):
        assert current_location_key(50.58727, 8.67554) == "giessen"

    def test_matches_sassofortino(self):
        assert current_location_key(43.02583, 11.11222) == "sassofortino"

    def test_no_match_for_custom_coordinates(self):
        assert current_location_key(0.0, 0.0) is None


class TestResolveLocation:
    def test_known_key(self):
        loc = resolve_location("giessen")
        assert loc is not None
        assert loc.label == "Gießen, DE"

    def test_unknown_key_returns_none(self):
        assert resolve_location("nowhere") is None


class TestLocationDisplayName:
    def test_preset_returns_place_name_without_country_suffix(self):
        assert location_display_name(50.58727, 8.67554) == "Gießen"
        assert location_display_name(43.02583, 11.11222) == "Sassofortino"

    def test_custom_coordinates_fall_back_to_lat_lon(self):
        name = location_display_name(51.5074, -0.1278)
        assert "51.51" in name
        assert "-0.13" in name

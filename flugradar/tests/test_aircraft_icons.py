"""Unit tests for ADS-B category / type-code aircraft classification and icons."""

import pygame
import pytest

from flugradar.display.aircraft_icons import (
    _JET_HALF,
    _WIDE_HALF,
    classify_type,
    draw_plane_icon,
)


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


class TestClassifyByCategory:
    """ADS-B emitter category is the primary classification source."""

    @pytest.mark.parametrize(
        "category,expected",
        [
            ("A1", "light"),
            ("A2", "jet"),
            ("A3", "jet"),
            ("A4", "wide"),
            ("A5", "wide"),
            ("A6", "fighter"),
            ("A7", "helicopter"),
            ("B1", "glider"),
            ("B2", "generic"),
            ("B4", "light"),
            ("B6", "drone"),
            ("B7", "generic"),
            ("c3", "generic"),  # lower-case input normalised
        ],
    )
    def test_category_maps_to_icon(self, category, expected):
        assert classify_type("", category) == expected

    def test_category_overrides_conflicting_type_code(self):
        # A320 would classify as "jet" by type code alone, but a reported
        # rotorcraft category must win since it reflects the real aircraft.
        assert classify_type("A320", "A7") == "helicopter"


class TestClassifyFallbackToTypeCode:
    """When category is missing or a 'no info' code, fall back to type code."""

    def test_no_category_uses_type_code(self):
        assert classify_type("C172") == "prop"
        assert classify_type("B738") == "jet"

    @pytest.mark.parametrize("no_info", [None, "", "A0", "B0"])
    def test_no_info_category_falls_back(self, no_info):
        assert classify_type("C172", no_info) == "prop"

    def test_nothing_known_returns_generic(self):
        assert classify_type("", None) == "generic"
        assert classify_type() == "generic"

    def test_unmatched_type_code_defaults_to_jet(self):
        assert classify_type("XYZ9") == "jet"


class TestWideBodySilhouette:
    def test_wide_is_not_a_uniform_scale_of_jet(self):
        jet_ratio = max(x for x, _ in _JET_HALF) / max(y for _, y in _JET_HALF)
        wide_ratio = max(x for x, _ in _WIDE_HALF) / max(y for _, y in _WIDE_HALF)
        assert abs(jet_ratio - wide_ratio) > 0.05


class TestDrawPlaneIconSmoke:
    @pytest.mark.parametrize(
        "aircraft_type,category",
        [
            ("A320", None),
            ("", "A1"),   # light
            ("", "A5"),   # wide
            ("", "A6"),   # fighter
            ("", "A7"),   # helicopter
            ("C172", None),  # prop
            ("", "B1"),   # glider
            ("", "B6"),   # drone
            ("", None),   # generic
        ],
    )
    def test_draw_does_not_crash(self, aircraft_type, category):
        surf = pygame.Surface((100, 100), pygame.SRCALPHA)
        draw_plane_icon(
            surf, 50, 50, 45.0, (255, 255, 255),
            aircraft_type=aircraft_type, category=category,
        )

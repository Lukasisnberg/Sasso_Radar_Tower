"""Unit tests for ADS-B category / type-code aircraft classification and icons."""

import pygame
import pytest

import flugradar.display.aircraft_icons as aircraft_icons
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

    @pytest.mark.parametrize("icon_set", ["detailed", "simple"])
    def test_draw_does_not_crash_either_icon_set(self, icon_set):
        surf = pygame.Surface((100, 100), pygame.SRCALPHA)
        draw_plane_icon(
            surf, 50, 50, 123.0, (200, 150, 50),
            aircraft_type="B747", icon_set=icon_set,
        )


class TestDetailedIconCache:
    def setup_method(self):
        aircraft_icons._raw_surface_cache.clear()
        aircraft_icons._render_cache.clear()
        aircraft_icons._warned_missing.clear()

    def test_same_combo_returns_cached_object(self):
        s1 = aircraft_icons._get_rendered_icon("a320", 30, (10, 20, 30), 44.0)
        s2 = aircraft_icons._get_rendered_icon("a320", 30, (10, 20, 30), 46.0)
        assert s1 is s2  # 44 and 46 both round to the same 5-degree bucket

    def test_different_angle_bucket_not_cached_together(self):
        s1 = aircraft_icons._get_rendered_icon("a320", 30, (10, 20, 30), 0.0)
        s2 = aircraft_icons._get_rendered_icon("a320", 30, (10, 20, 30), 90.0)
        assert s1 is not s2

    def test_missing_icon_falls_back_to_generic_without_crash(self):
        result = aircraft_icons._get_rendered_icon(
            "definitely_not_a_real_icon", 20, (1, 2, 3), 0.0
        )
        assert result is not None
        assert "definitely_not_a_real_icon" in aircraft_icons._warned_missing

    def test_missing_icon_warns_only_once(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        aircraft_icons._get_rendered_icon("still_not_real", 20, (1, 2, 3), 0.0)
        aircraft_icons._get_rendered_icon("still_not_real", 20, (1, 2, 3), 0.0)
        warnings = [r for r in caplog.records if "still_not_real" in r.message]
        assert len(warnings) == 1

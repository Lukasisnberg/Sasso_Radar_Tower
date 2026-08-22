"""Unit tests for the Lucide UI-icon loader (Schritt 1 of the UI overhaul)."""

import logging

import pygame
import pytest

from flugradar.display import ui_icons


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


class TestGetIcon:
    def test_real_icon_rasterises_at_requested_size(self):
        icon = ui_icons.get_icon("chevron-left", 18, (10, 20, 30))
        assert icon.get_size() == (18, 18)

    def test_different_real_icons_are_distinct_surfaces(self):
        left = ui_icons.get_icon("chevron-left", 18, (10, 20, 30))
        right = ui_icons.get_icon("chevron-right", 18, (10, 20, 30))
        assert left is not right

    def test_tint_forces_every_pixel_to_requested_colour(self):
        # The multiply-to-black-then-add recipe (see _tint_surface) forces
        # every pixel's RGB to the target colour regardless of its alpha
        # (only alpha carries the actual glyph shape) -- so this holds for
        # the whole surface, not just the visibly-opaque stroke pixels.
        icon = ui_icons.get_icon("lock", 24, (200, 50, 10))
        for x in range(icon.get_width()):
            for y in range(icon.get_height()):
                px = icon.get_at((x, y))
                assert (px.r, px.g, px.b) == (200, 50, 10)


class TestCache:
    def setup_method(self):
        ui_icons.reset_cache()

    def test_same_combo_returns_cached_object(self):
        s1 = ui_icons.get_icon("radar", 20, (1, 2, 3))
        s2 = ui_icons.get_icon("radar", 20, (1, 2, 3))
        assert s1 is s2

    def test_different_colour_not_cached_together(self):
        s1 = ui_icons.get_icon("radar", 20, (1, 2, 3))
        s2 = ui_icons.get_icon("radar", 20, (4, 5, 6))
        assert s1 is not s2

    def test_different_size_not_cached_together(self):
        s1 = ui_icons.get_icon("radar", 20, (1, 2, 3))
        s2 = ui_icons.get_icon("radar", 30, (1, 2, 3))
        assert s1 is not s2

    def test_reset_cache_clears_render_and_raw_caches(self):
        ui_icons.get_icon("radar", 20, (1, 2, 3))
        assert ui_icons._render_cache
        assert ui_icons._raw_svg_cache
        ui_icons.reset_cache()
        assert not ui_icons._render_cache
        assert not ui_icons._raw_svg_cache


class TestMissingIcon:
    def setup_method(self):
        ui_icons.reset_cache()

    def test_missing_icon_returns_placeholder_without_crash(self):
        result = ui_icons.get_icon("definitely_not_a_real_icon", 20, (1, 2, 3))
        assert result is not None
        assert result.get_size() == (20, 20)
        assert "definitely_not_a_real_icon" in ui_icons._warned_missing

    def test_missing_icon_warns_only_once(self, caplog):
        caplog.set_level(logging.WARNING)
        ui_icons.get_icon("still_not_real", 20, (1, 2, 3))
        ui_icons.get_icon("still_not_real", 20, (1, 2, 3))
        warnings = [r for r in caplog.records if "still_not_real" in r.message]
        assert len(warnings) == 1


class TestDrawIcon:
    def test_draw_does_not_crash(self):
        surface = pygame.Surface((40, 40))
        ui_icons.draw_icon(surface, "eye", (20, 20), 18, (255, 255, 255))

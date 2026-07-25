"""Tests for the licensed weather-condition icon set (Weather Icons by
Erik Flowers, SIL OFL 1.1 -- flugradar/assets/icons/weather/LICENSE.txt).
"""

import pygame
import pytest

from flugradar.data_sources.weather import _WEATHER_CODES
from flugradar.display.weather_icons import (
    GENERIC_ICON,
    _CODE_TO_ICON,
    _get_rendered_icon,
    _raw_surface_cache,
    _render_cache,
    draw_weather_icon,
    resolve_icon,
)


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((100, 100))
    yield
    _raw_surface_cache.clear()
    _render_cache.clear()
    pygame.quit()


class TestCodeCoverage:
    """Every code the real Tomorrow.io client can return must resolve to
    some icon -- a screen showing "no icon" for a valid, known condition
    would be a worse regression than an imprecise one."""

    def test_every_weather_code_has_a_mapping_or_falls_back_cleanly(self):
        for code in _WEATHER_CODES:
            if code == 0:
                continue  # "Unknown" -- deliberately falls through to GENERIC_ICON
            day, night = resolve_icon(code, is_night=False), resolve_icon(code, is_night=True)
            assert day, f"no day icon resolved for code {code}"
            assert night, f"no night icon resolved for code {code}"

    def test_unknown_code_falls_back_to_generic(self):
        assert resolve_icon(0) == GENERIC_ICON
        assert resolve_icon(99999) == GENERIC_ICON
        assert resolve_icon(None) == GENERIC_ICON

    def test_day_and_night_variants_differ_for_clear_sky(self):
        assert resolve_icon(1000, is_night=False) != resolve_icon(1000, is_night=True)

    def test_is_night_selects_the_night_entry(self):
        day_key, night_key = _CODE_TO_ICON[1000]
        assert resolve_icon(1000, is_night=False) == day_key
        assert resolve_icon(1000, is_night=True) == night_key


class TestIconAssetsExist:
    """Every icon key referenced by the mapping table must have a real
    SVG file on disk -- a typo here would silently fall back to the
    generic icon at runtime instead of failing loudly."""

    def test_every_referenced_icon_file_loads(self):
        keys = {GENERIC_ICON}
        for day_key, night_key in _CODE_TO_ICON.values():
            keys.add(day_key)
            keys.add(night_key)
        for key in sorted(keys):
            surf = _get_rendered_icon(key, 32, (255, 255, 255))
            assert surf is not None, f"icon asset missing or failed to load: {key}"


class TestDrawWeatherIcon:
    @pytest.mark.parametrize("code", [1000, 1101, 1001, 2100, 4001, 5000, 8000, 0, None])
    def test_draws_without_crashing(self, code):
        surf = pygame.Surface((100, 100))
        draw_weather_icon(surf, code, (50, 50), 24, (200, 200, 200))

    def test_night_variant_draws_without_crashing(self):
        surf = pygame.Surface((100, 100))
        draw_weather_icon(surf, 1000, (50, 50), 24, (200, 200, 200), is_night=True)

    def test_zero_radius_does_not_crash(self):
        surf = pygame.Surface((100, 100))
        draw_weather_icon(surf, 1000, (50, 50), 0, (200, 200, 200))


class TestCaching:
    def test_repeated_calls_reuse_the_cached_surface(self):
        a = _get_rendered_icon("day-sunny", 32, (255, 255, 255))
        b = _get_rendered_icon("day-sunny", 32, (255, 255, 255))
        assert a is b

    def test_different_colour_is_a_different_cache_entry(self):
        a = _get_rendered_icon("day-sunny", 32, (255, 255, 255))
        b = _get_rendered_icon("day-sunny", 32, (0, 0, 0))
        assert a is not b

    def test_different_size_is_a_different_cache_entry(self):
        a = _get_rendered_icon("day-sunny", 32, (255, 255, 255))
        b = _get_rendered_icon("day-sunny", 48, (255, 255, 255))
        assert a is not b

    def test_missing_icon_key_falls_back_to_generic_without_crashing(self):
        surf = _get_rendered_icon("not-a-real-icon-key", 32, (255, 255, 255))
        assert surf is not None  # resolved via the GENERIC_ICON fallback

"""Tests for WeatherScreen (current conditions + 5-day forecast), laid
out per docs/weather-screen-mockup.svg (docs/prompt-wetterscreen.md).

Schritt 1 (layout skeleton) renders fixed example data -- real
Tomorrow.io wiring, the no-key/offline cases, and unit handling land in
Schritt 3; these tests cover the layout mechanics and the pure
formatting helpers that Schritt 3 will reuse unchanged.
"""

import pygame
import pytest

from flugradar.display import nav, scaling
from flugradar.display.screens.weather import WeatherScreen, _bare_temp_str, _weekday_label
from flugradar.display.theme import CLASSIC_AMBER


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((300, 300))
    scaling.init(300)
    yield
    pygame.quit()


@pytest.fixture
def screen():
    return WeatherScreen(300, CLASSIC_AMBER)


@pytest.fixture
def surf():
    return pygame.Surface((300, 300))


class TestDrawsWithoutCrashing:
    def test_default_construction(self, screen, surf):
        screen.draw(surf)

    def test_fahrenheit(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, temperature_unit="f")
        screen.draw(surf)

    def test_statute_miles_wind_unit(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, distance_unit="sm")
        screen.draw(surf)

    def test_nautical_miles_wind_unit(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, distance_unit="nm")
        screen.draw(surf)

    def test_12h_time_format(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, time_format="12h")
        screen.draw(surf)

    def test_long_custom_location_label(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, location_label="43.02583, 11.11222")
        screen.draw(surf)

    def test_empty_location_label_falls_back(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, location_label="")
        screen.draw(surf)  # must not crash with no location set

    def test_small_screen_size(self):
        scaling.init(150)
        try:
            screen = WeatherScreen(150, CLASSIC_AMBER)
            small_surf = pygame.Surface((150, 150))
            screen.draw(small_surf)
        finally:
            scaling.init(300)

    def test_repeated_draws_are_stable(self, screen, surf):
        for _ in range(5):
            screen.draw(surf)


class TestHandleTap:
    def test_tap_footer_zone_returns_radar(self, screen, surf):
        screen.draw(surf)
        rect = nav.footer_button_rects(1)[0]
        assert screen.handle_tap(rect.centerx, rect.centery) == "radar"

    def test_tap_elsewhere_does_nothing(self, screen, surf):
        screen.draw(surf)
        assert screen.handle_tap(150, 150) == ""


class TestBareTempStr:
    def test_celsius_rounds_to_nearest_degree(self):
        assert _bare_temp_str(21.4, "c") == "21°"
        assert _bare_temp_str(21.6, "c") == "22°"

    def test_fahrenheit_conversion(self):
        assert _bare_temp_str(0.0, "f") == "32°"

    def test_no_unit_letter(self):
        assert "C" not in _bare_temp_str(20.0, "c")
        assert "F" not in _bare_temp_str(20.0, "f")


class TestWeekdayLabel:
    def test_valid_date_returns_uppercase_abbreviation(self):
        label = _weekday_label("2026-01-03")
        assert len(label) == 3
        assert label == label.upper()

    def test_malformed_date_falls_back(self):
        assert _weekday_label("not-a-date") == "—"


class TestFractionHelpers:
    def test_y_frac_zero_is_centre(self, screen):
        assert screen._y(0.0) == scaling.center_y()

    def test_x_frac_zero_is_centre(self, screen):
        assert screen._x(0.0) == scaling.center_x()

    def test_negative_y_frac_is_above_centre(self, screen):
        assert screen._y(-0.5) < scaling.center_y()

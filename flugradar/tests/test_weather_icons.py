"""Tests for the hand-drawn weather condition icons."""

import pygame
import pytest

from flugradar.display.weather_icons import category_for_code, draw_weather_icon


class TestCategoryForCode:
    def test_clear(self):
        assert category_for_code(1000) == "clear"

    def test_partly_cloudy(self):
        assert category_for_code(1101) == "partly_cloudy"

    def test_cloudy(self):
        assert category_for_code(1001) == "cloudy"

    def test_fog(self):
        assert category_for_code(2100) == "fog"

    def test_rain(self):
        assert category_for_code(4001) == "rain"

    def test_freezing_rain_maps_to_rain(self):
        assert category_for_code(6201) == "rain"

    def test_snow(self):
        assert category_for_code(5000) == "snow"

    def test_ice_pellets_map_to_snow(self):
        assert category_for_code(7000) == "snow"

    def test_thunderstorm(self):
        assert category_for_code(8000) == "thunderstorm"

    def test_unknown_code_falls_back_to_cloudy(self):
        assert category_for_code(99999) == "cloudy"

    def test_none_falls_back_to_cloudy(self):
        assert category_for_code(None) == "cloudy"


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((100, 100))
    yield
    pygame.quit()


class TestDrawWeatherIcon:
    @pytest.mark.parametrize("code", [1000, 1101, 1001, 2100, 4001, 5000, 8000, None])
    def test_draws_without_crashing(self, code):
        surf = pygame.Surface((100, 100))
        draw_weather_icon(surf, code, (50, 50), 24, (200, 200, 200), (255, 180, 0))

    def test_zero_radius_does_not_crash(self):
        surf = pygame.Surface((100, 100))
        draw_weather_icon(surf, 1000, (50, 50), 0, (200, 200, 200), (255, 180, 0))

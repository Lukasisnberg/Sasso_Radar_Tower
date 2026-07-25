"""Tests for WeatherScreen (3-day forecast)."""

import pygame
import pytest

from flugradar.data_sources.weather import DailyForecast
from flugradar.display import scaling
from flugradar.display.screens.weather import WeatherScreen
from flugradar.display.theme import CLASSIC_AMBER

_SAMPLE_FORECAST = [
    DailyForecast(date="2026-07-25", temp_min_c=14.0, temp_max_c=26.0, weather_code=1101, condition="Partly Cloudy"),
    DailyForecast(date="2026-07-26", temp_min_c=15.0, temp_max_c=28.0, weather_code=4001, condition="Rain"),
    DailyForecast(date="2026-07-27", temp_min_c=13.0, temp_max_c=24.0, weather_code=8000, condition="Thunderstorm"),
]


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


class TestNoApiKey:
    def test_draws_without_crashing(self, screen, surf):
        screen.set_forecast([], has_key=False)
        screen.draw(surf)

    def test_footer_radar_button_still_works(self, screen, surf):
        screen.set_forecast([], has_key=False)
        screen.draw(surf)
        from flugradar.display import nav
        rect = nav.footer_button_rects(1)[0]
        assert screen.handle_tap(rect.centerx, rect.centery) == "radar"


class TestNoForecastData:
    def test_draws_without_crashing(self, screen, surf):
        screen.set_forecast([], has_key=True)
        screen.draw(surf)


class TestWithForecast:
    def test_draws_without_crashing(self, screen, surf):
        screen.set_forecast(_SAMPLE_FORECAST, has_key=True)
        screen.draw(surf)

    def test_only_first_three_days_used(self, screen, surf):
        extra = _SAMPLE_FORECAST + [
            DailyForecast(date="2026-07-28", temp_min_c=10.0, temp_max_c=20.0, weather_code=1000, condition="Clear")
        ]
        screen.set_forecast(extra, has_key=True)
        screen.draw(surf)  # must not raise even with 4 entries stored


class TestHandleTap:
    def test_tap_footer_radar(self, screen, surf):
        screen.set_forecast(_SAMPLE_FORECAST, has_key=True)
        screen.draw(surf)
        from flugradar.display import nav
        rect = nav.footer_button_rects(1)[0]
        assert screen.handle_tap(rect.centerx, rect.centery) == "radar"

    def test_tap_elsewhere_does_nothing(self, screen, surf):
        screen.set_forecast(_SAMPLE_FORECAST, has_key=True)
        screen.draw(surf)
        assert screen.handle_tap(150, 150) == ""


class TestDayLabel:
    def test_today_label(self):
        from flugradar.display.screens.weather import _day_label
        assert _day_label("2026-07-25", 0) == "Today"

    def test_other_day_label_is_weekday_abbreviation(self):
        from flugradar.display.screens.weather import _day_label
        label = _day_label("2026-07-26", 1)
        assert len(label) == 3

    def test_malformed_date_falls_back_to_raw_string(self):
        from flugradar.display.screens.weather import _day_label
        assert _day_label("not-a-date", 1) == "not-a-date"

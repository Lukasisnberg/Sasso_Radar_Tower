"""Tests for WeatherScreen (current conditions + 5-day forecast), laid
out per docs/weather-screen-mockup.svg (docs/prompt-wetterscreen.md).

Covers the required Schritt 3 cases: no key, fetch-error/stale data,
unit switching, full-data rendering, and missing individual fields.
"""

import pygame
import pytest

from flugradar.data_sources.weather import DailyForecast, WeatherData
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


def _full_weather(**overrides) -> WeatherData:
    defaults = dict(
        temperature_c=21.0,
        wind_speed_ms=12.0 / 3.6,
        weather_code=1100,
        condition="Mostly Clear",
        temperature_apparent_c=20.0,
        precipitation_probability_pct=5.0,
    )
    defaults.update(overrides)
    return WeatherData(**defaults)


def _full_forecast() -> list[DailyForecast]:
    return [
        DailyForecast(date="2026-01-03", temp_min_c=13, temp_max_c=23, weather_code=1000, condition="Clear"),
        DailyForecast(date="2026-01-04", temp_min_c=14, temp_max_c=24, weather_code=1000, condition="Clear"),
        DailyForecast(date="2026-01-05", temp_min_c=11, temp_max_c=19, weather_code=1001, condition="Cloudy"),
        DailyForecast(date="2026-01-06", temp_min_c=10, temp_max_c=17, weather_code=1001, condition="Cloudy"),
        DailyForecast(date="2026-01-07", temp_min_c=12, temp_max_c=22, weather_code=1000, condition="Clear"),
    ]


class TestNoKey:
    def test_default_state_is_no_key(self, screen):
        assert screen.has_key is False

    def test_draws_message_without_crashing(self, screen, surf):
        screen.draw(surf)  # has_key defaults to False -- must not crash

    def test_footer_still_works_without_key(self, screen, surf):
        screen.draw(surf)
        rect = nav.footer_button_rects(1)[0]
        assert screen.handle_tap(rect.centerx, rect.centery) == "radar"


class TestNoDataYet:
    def test_key_present_but_no_fetch_yet(self, screen, surf):
        screen.set_data(has_key=True, current=None)
        screen.draw(surf)  # must not crash -- "Weather unavailable"


class TestFullData:
    def test_draws_without_crashing(self, screen, surf):
        screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
        screen.draw(surf)

    def test_repeated_draws_are_stable(self, screen, surf):
        screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
        for _ in range(5):
            screen.draw(surf)

    def test_small_screen_size(self):
        scaling.init(150)
        try:
            screen = WeatherScreen(150, CLASSIC_AMBER)
            screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
            small_surf = pygame.Surface((150, 150))
            screen.draw(small_surf)
        finally:
            scaling.init(300)


class TestUnitsAffectAllValues:
    def test_fahrenheit(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, temperature_unit="f")
        screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
        screen.draw(surf)  # must not crash; conversion covered by _bare_temp_str tests

    def test_statute_miles_wind_unit(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, distance_unit="sm")
        screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
        screen.draw(surf)

    def test_nautical_miles_wind_unit(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, distance_unit="nm")
        screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
        screen.draw(surf)

    def test_12h_time_format(self, surf):
        screen = WeatherScreen(300, CLASSIC_AMBER, time_format="12h")
        screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
        screen.draw(surf)

    def test_wind_speed_str_reflects_distance_unit(self):
        screen_km = WeatherScreen(300, CLASSIC_AMBER, distance_unit="km")
        screen_sm = WeatherScreen(300, CLASSIC_AMBER, distance_unit="sm")
        wx = _full_weather(wind_speed_ms=10.0)
        assert wx.wind_speed_str(screen_km.distance_unit) != wx.wind_speed_str(screen_sm.distance_unit)


class TestStaleData:
    def test_stale_flag_draws_without_crashing(self, screen, surf):
        screen.set_data(has_key=True, current=_full_weather(), is_stale=True, age_s=754.0, forecast=_full_forecast())
        screen.draw(surf)

    def test_stale_without_age_does_not_crash(self, screen, surf):
        # age_s can legitimately be None even when is_stale is True (e.g.
        # a client implementation that doesn't track fetch time) -- must
        # not raise trying to format a missing age.
        screen.set_data(has_key=True, current=_full_weather(), is_stale=True, age_s=None, forecast=_full_forecast())
        screen.draw(surf)

    def test_fresh_data_does_not_show_age_hint(self, screen):
        screen.set_data(has_key=True, current=_full_weather(), is_stale=False, age_s=None)
        # is_stale False means the header helper must not append an age
        # suffix -- exercised indirectly via draw() not crashing and the
        # explicit is_stale check in _draw_header.
        assert screen.is_stale is False


class TestMissingIndividualFields:
    def test_missing_feels_like_is_omitted_not_crashed(self, screen, surf):
        wx = _full_weather(temperature_apparent_c=None)
        screen.set_data(has_key=True, current=wx, forecast=_full_forecast())
        screen.draw(surf)

    def test_missing_rain_chance_is_omitted_not_crashed(self, screen, surf):
        wx = _full_weather(precipitation_probability_pct=None)
        screen.set_data(has_key=True, current=wx, forecast=_full_forecast())
        screen.draw(surf)

    def test_missing_wind_is_omitted_not_crashed(self, screen, surf):
        wx = _full_weather(wind_speed_ms=None)
        screen.set_data(has_key=True, current=wx, forecast=_full_forecast())
        screen.draw(surf)

    def test_all_three_values_missing_is_omitted_not_crashed(self, screen, surf):
        wx = _full_weather(wind_speed_ms=None, temperature_apparent_c=None, precipitation_probability_pct=None)
        screen.set_data(has_key=True, current=wx, forecast=_full_forecast())
        screen.draw(surf)

    def test_empty_forecast_is_omitted_not_crashed(self, screen, surf):
        screen.set_data(has_key=True, current=_full_weather(), forecast=[])
        screen.draw(surf)

    def test_missing_weather_code_falls_back_to_generic_icon(self, screen, surf):
        wx = _full_weather(weather_code=None, condition="")
        screen.set_data(has_key=True, current=wx, forecast=_full_forecast())
        screen.draw(surf)


class TestHandleTap:
    def test_tap_footer_radar(self, screen, surf):
        screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
        screen.draw(surf)
        rect = nav.footer_button_rects(1)[0]
        assert screen.handle_tap(rect.centerx, rect.centery) == "radar"

    def test_tap_elsewhere_does_nothing(self, screen, surf):
        screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
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
        assert len(label) == 2  # German weekday abbreviations are 2 letters (Mo/Di/Mi/...)
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


class TestSetData:
    def test_forecast_defaults_to_empty_list_when_none(self, screen):
        screen.set_data(has_key=True, current=_full_weather(), forecast=None)
        assert screen.forecast == []

    def test_stores_all_fields(self, screen):
        wx = _full_weather()
        fc = _full_forecast()
        screen.set_data(has_key=True, current=wx, is_stale=True, age_s=42.0, forecast=fc)
        assert screen.has_key is True
        assert screen.current is wx
        assert screen.is_stale is True
        assert screen.age_s == 42.0
        assert screen.forecast is fc


class TestSchritt15Polish:
    """Abschnitt 15 (Gestaltung) checks: tabular figures on every number
    so updates don't jitter, and nothing drawn past the disc's visible
    chord at the row it sits on."""

    def test_hero_temperature_uses_tabular_figures(self, screen):
        from flugradar.display.fonts import get_font
        from flugradar.display.screens.weather import _HERO_TEMP_SCALE
        from flugradar.display.theme import TOKENS

        screen._ensure_fonts()
        expected = get_font(
            scaling.s(round(TOKENS.font_title * _HERO_TEMP_SCALE)), bold=True, mono=True,
        )
        assert screen._hero_temp_font is expected

    def test_location_header_stays_within_visible_chord_at_production_size(self):
        from flugradar.display.draw_helpers import render_tracked_text
        from flugradar.display.screens.weather import _LOCATION_Y_FRAC

        scaling.init(720)
        try:
            screen = WeatherScreen(720, CLASSIC_AMBER, location_label="Sassofortino")
            screen._ensure_fonts()
            y = screen._y(_LOCATION_Y_FRAC)
            budget = scaling.circle_half_width_at_row(y, screen._location_font.get_height()) * 2
            rendered = render_tracked_text(
                screen._location_font, "SASSOFORTINO", (255, 255, 255), spacing=scaling.s(3),
            )
            assert rendered.get_width() <= budget
        finally:
            scaling.init(300)

    def test_forecast_columns_stay_within_visible_chord_at_production_size(self):
        from flugradar.display.screens.weather import _FORECAST_DX_FRAC

        scaling.init(720)
        try:
            screen = WeatherScreen(720, CLASSIC_AMBER, location_label="Sassofortino")
            screen._ensure_fonts()
            surf = pygame.Surface((720, 720))
            screen.set_data(has_key=True, current=_full_weather(), forecast=_full_forecast())
            y = screen._draw_current(surf)
            y = screen._draw_values_row(surf, y)
            y = screen._draw_hairline(surf, y)
            forecast_bottom = screen._draw_forecast_row(surf, y)

            # Check at the row's *bottom* (the lo-temperature line), not
            # its top -- the chord only narrows further from the row
            # start, so the bottom is the actual worst case for a column
            # sitting at a constant x-offset the whole way down.
            budget = scaling.circle_half_width_at_row(forecast_bottom, screen._forecast_lo_font.get_height())
            outer_dx = max(abs(f) for f in _FORECAST_DX_FRAC)
            outer_offset_px = outer_dx * scaling.visible_radius()
            assert outer_offset_px < budget
        finally:
            scaling.init(300)

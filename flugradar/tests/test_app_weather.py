"""RadarApp wiring for the Weather screen: navigation gestures, feeding
the screen from the shared WeatherClient, and rebuilding the Tomorrow.io
client on a live settings change (the actual fix for "saved a key in the
portal but it's not picked up")."""

from unittest.mock import MagicMock

import pygame
import pytest

from flugradar.config import settings as settings_mod
from flugradar.config.settings import AppSettings
from flugradar.data_sources.weather import DailyForecast, WeatherData
from flugradar.display import scaling
from flugradar.display.app import ActiveScreen, RadarApp
from flugradar.display.gestures import Gesture, GestureType


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((200, 200))
    scaling.init(200)
    yield
    pygame.quit()


@pytest.fixture
def settings(tmp_path, monkeypatch):
    portal_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
    return AppSettings()


@pytest.fixture
def app(settings):
    return RadarApp(settings, screen_size=200, demo_mode=True)


def _fake_screens():
    """MagicMocks stand in for the six screens _apply_live_settings/
    _handle_gesture normally receive -- they only ever have attributes
    set or no-op methods called on them by these two functions."""
    return {
        "radar": MagicMock(), "detail": MagicMock(), "clock_scr": MagicMock(),
        "about": MagicMock(), "menu": MagicMock(), "tracking_scr": MagicMock(),
        "weather_scr": MagicMock(), "proj": MagicMock(),
    }


class TestUpdateWeatherScreen:
    def test_no_client_reports_no_key(self, app, settings):
        weather_scr = MagicMock()
        app._weather_client = None
        settings.tomorrow_api_key = ""
        app._update_weather_screen(weather_scr)
        weather_scr.set_data.assert_called_once_with(False, None, False, None, [])

    def test_client_forwards_current_forecast_and_staleness(self, app, settings):
        weather_scr = MagicMock()
        settings.tomorrow_api_key = "abc123"
        current = WeatherData(temperature_c=20.0)
        forecast = [DailyForecast(date="2026-07-25", temp_min_c=10, temp_max_c=20)]
        fake_client = MagicMock()
        fake_client.get_weather.return_value = current
        fake_client.is_stale = True
        fake_client.weather_age_s.return_value = 754.0
        fake_client.get_forecast.return_value = forecast
        app._weather_client = fake_client

        app._update_weather_screen(weather_scr)

        fake_client.get_forecast.assert_called_once_with(days=5)
        weather_scr.set_data.assert_called_once_with(True, current, True, 754.0, forecast)

    def test_key_present_but_client_never_built_reports_no_data(self, app, settings):
        # e.g. a key was just saved but _apply_live_settings hasn't run
        # yet -- has_key should still reflect the setting even though
        # there's no client to ask for data.
        weather_scr = MagicMock()
        settings.tomorrow_api_key = "abc123"
        app._weather_client = None
        app._update_weather_screen(weather_scr)
        weather_scr.set_data.assert_called_once_with(True, None, False, None, [])


class TestClockToWeatherNavigation:
    def test_swipe_right_from_clock_opens_weather(self, app, settings):
        f = _fake_screens()
        app._active = ActiveScreen.CLOCK
        app._handle_gesture(
            Gesture(GestureType.SWIPE_RIGHT, 0, 0),
            f["radar"], f["detail"], f["clock_scr"], f["about"], f["menu"],
            f["tracking_scr"], f["weather_scr"], None, f["proj"], None,
        )
        assert app._active == ActiveScreen.WEATHER

    def test_swipe_left_from_weather_returns_to_clock(self, app, settings):
        f = _fake_screens()
        app._active = ActiveScreen.WEATHER
        app._handle_gesture(
            Gesture(GestureType.SWIPE_LEFT, 0, 0),
            f["radar"], f["detail"], f["clock_scr"], f["about"], f["menu"],
            f["tracking_scr"], f["weather_scr"], None, f["proj"], None,
        )
        assert app._active == ActiveScreen.CLOCK

    def test_swipe_down_from_weather_returns_to_clock(self, app, settings):
        f = _fake_screens()
        app._active = ActiveScreen.WEATHER
        app._handle_gesture(
            Gesture(GestureType.SWIPE_DOWN, 0, 0),
            f["radar"], f["detail"], f["clock_scr"], f["about"], f["menu"],
            f["tracking_scr"], f["weather_scr"], None, f["proj"], None,
        )
        assert app._active == ActiveScreen.CLOCK

    def test_tap_footer_radar_from_weather_goes_to_radar(self, app, settings):
        f = _fake_screens()
        f["weather_scr"].handle_tap.return_value = "radar"
        app._active = ActiveScreen.WEATHER
        app._handle_gesture(
            Gesture(GestureType.TAP, 5, 5),
            f["radar"], f["detail"], f["clock_scr"], f["about"], f["menu"],
            f["tracking_scr"], f["weather_scr"], None, f["proj"], None,
        )
        assert app._active == ActiveScreen.RADAR

    def test_tap_elsewhere_on_weather_stays(self, app, settings):
        f = _fake_screens()
        f["weather_scr"].handle_tap.return_value = ""
        app._active = ActiveScreen.WEATHER
        app._handle_gesture(
            Gesture(GestureType.TAP, 5, 5),
            f["radar"], f["detail"], f["clock_scr"], f["about"], f["menu"],
            f["tracking_scr"], f["weather_scr"], None, f["proj"], None,
        )
        assert app._active == ActiveScreen.WEATHER


class TestApplyLiveSettingsWeatherClient:
    """The actual bug fix: a key saved via the portal must be picked up
    without restarting the display app, not just on the next boot."""

    def test_builds_weather_client_when_key_appears(self, app, settings):
        f = _fake_screens()
        assert app._weather_client is None
        settings.tomorrow_api_key = "abc123"
        app._apply_live_settings(
            f["proj"], f["radar"], f["detail"], f["clock_scr"], f["about"],
            f["menu"], f["tracking_scr"], f["weather_scr"], None,
        )
        assert app._weather_client is not None
        assert app._weather_client._api_key == "abc123"

    def test_closes_weather_client_when_key_cleared(self, app, settings):
        f = _fake_screens()
        settings.tomorrow_api_key = "abc123"
        app._apply_live_settings(
            f["proj"], f["radar"], f["detail"], f["clock_scr"], f["about"],
            f["menu"], f["tracking_scr"], f["weather_scr"], None,
        )
        assert app._weather_client is not None

        settings.tomorrow_api_key = ""
        app._apply_live_settings(
            f["proj"], f["radar"], f["detail"], f["clock_scr"], f["about"],
            f["menu"], f["tracking_scr"], f["weather_scr"], None,
        )
        assert app._weather_client is None

    def test_updates_weather_screen_theme_and_units(self, app, settings):
        f = _fake_screens()
        settings.temperature_unit = "f"
        settings.distance_unit = "sm"
        settings.time_format = "12h"
        app._apply_live_settings(
            f["proj"], f["radar"], f["detail"], f["clock_scr"], f["about"],
            f["menu"], f["tracking_scr"], f["weather_scr"], None,
        )
        assert f["weather_scr"].temperature_unit == "f"
        assert f["weather_scr"].distance_unit == "sm"
        assert f["weather_scr"].time_format == "12h"
        assert f["weather_scr"].theme is app._theme

    def test_updates_weather_screen_location_label(self, app, settings):
        f = _fake_screens()
        settings.home.lat = 43.02583
        settings.home.lon = 11.11222
        app._apply_live_settings(
            f["proj"], f["radar"], f["detail"], f["clock_scr"], f["about"],
            f["menu"], f["tracking_scr"], f["weather_scr"], None,
        )
        assert f["weather_scr"].location_label == "Sassofortino"

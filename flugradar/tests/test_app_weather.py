"""RadarApp wiring for the Weather screen: navigation gestures, and
rebuilding the Tomorrow.io client on a live settings change (the actual
fix for "saved a key in the portal but it's not picked up")."""

from unittest.mock import MagicMock

import pygame
import pytest

from flugradar.config import settings as settings_mod
from flugradar.config.settings import AppSettings
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

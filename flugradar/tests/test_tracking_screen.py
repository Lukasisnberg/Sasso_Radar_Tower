"""Tests for TrackedFlightScreen (Ausbaustufe 2, Schritt 5).

Covers the four edge cases from docs/prompt-ausbaustufe-2.md 5.3: no
flight selected, no route known, aircraft out of range, and the footer
"stop" action -- each must produce a defined screen, never an empty one
or a crash.
"""

import pygame
import pytest

from flugradar.data_sources.models import Aircraft
from flugradar.display import scaling
from flugradar.display.screens.tracking import TrackedFlightScreen
from flugradar.display.theme import CLASSIC_AMBER

FRA = (50.033333, 8.570556)
JFK = (40.639801, -73.7789)


def _aircraft_with_route(**overrides):
    defaults = dict(
        icao_hex="4b1805", callsign="DLH400", lat=45.0, lon=-30.0,
        altitude_ft=35000, ground_speed_kt=480, vertical_rate_fpm=0,
        aircraft_type="A359", origin="FRA", destination="JFK",
        origin_lat=FRA[0], origin_lon=FRA[1],
        destination_lat=JFK[0], destination_lon=JFK[1],
    )
    defaults.update(overrides)
    return Aircraft(**defaults)


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((300, 300))
    scaling.init(300)
    yield
    pygame.quit()


@pytest.fixture
def screen():
    return TrackedFlightScreen(300, CLASSIC_AMBER)


@pytest.fixture
def surf():
    return pygame.Surface((300, 300))


class TestNoFlightSelected:
    def test_draws_without_crashing(self, screen, surf):
        screen.set_tracking(None, False, None)
        screen.draw(surf)  # must not raise

    def test_tap_in_dead_zone_does_nothing(self, screen, surf):
        screen.set_tracking(None, False, None)
        screen.draw(surf)
        # centre of the screen -- not the breadcrumb back-zone, not a footer button
        assert screen.handle_tap(150, 150) == ""

    def test_only_radar_footer_button_present(self, screen):
        screen.set_tracking(None, False, None)
        buttons = screen._footer_buttons_state()
        assert buttons == ["radar"]


class TestRouteKnown:
    def test_draws_progress_bar_without_crashing(self, screen, surf):
        screen.set_tracking(_aircraft_with_route(), True, None)
        screen.draw(surf)

    def test_footer_has_stop_and_radar(self, screen):
        screen.set_tracking(_aircraft_with_route(), True, None)
        assert screen._footer_buttons_state() == ["stop", "radar"]


class TestRouteUnknown:
    def test_no_coordinates_falls_back_to_live_data_only(self, screen, surf):
        ac = Aircraft(icao_hex="x", callsign="TEST1", lat=45.0, lon=-30.0, altitude_ft=10000)
        screen.set_tracking(ac, True, None)
        screen.draw(surf)  # must not crash / must not require route data

    def test_codes_known_but_no_coordinates_still_renders(self, screen, surf):
        ac = Aircraft(
            icao_hex="x", callsign="TEST1", lat=45.0, lon=-30.0,
            origin="FRA", destination="JFK",  # codes only, no lat/lon
        )
        screen.set_tracking(ac, True, None)
        screen.draw(surf)


class TestOutOfRange:
    def test_stale_aircraft_still_renders(self, screen, surf):
        screen.set_tracking(_aircraft_with_route(), False, 245.0)
        screen.draw(surf)

    def test_stale_but_never_had_route_renders(self, screen, surf):
        ac = Aircraft(icao_hex="x", callsign="TEST1", lat=45.0, lon=-30.0)
        screen.set_tracking(ac, False, 60.0)
        screen.draw(surf)


class TestZeroSpeedEta:
    def test_zero_ground_speed_does_not_crash(self, screen, surf):
        ac = _aircraft_with_route(ground_speed_kt=0)
        screen.set_tracking(ac, True, None)
        screen.draw(surf)

    def test_none_ground_speed_does_not_crash(self, screen, surf):
        ac = _aircraft_with_route(ground_speed_kt=None)
        screen.set_tracking(ac, True, None)
        screen.draw(surf)


class TestFooterStop:
    def test_stop_button_present_only_when_flight_selected(self, screen):
        screen.set_tracking(None, False, None)
        assert "stop" not in screen._footer_buttons_state()
        screen.set_tracking(_aircraft_with_route(), True, None)
        assert "stop" in screen._footer_buttons_state()

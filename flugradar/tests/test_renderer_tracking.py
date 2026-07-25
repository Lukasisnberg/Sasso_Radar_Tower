"""Tracked-flight highlighting on the radar (Ausbaustufe 2, Schritt 5, 5.4:
"Auf dem Radar wird der getrackte Flug mit der Akzentfarbe hervorgehoben")."""

import pygame
import pytest

from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.projection import ScreenProjection
from flugradar.display import scaling
from flugradar.display.renderer import RadarRenderer
from flugradar.display.theme import CLASSIC_AMBER


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    scaling.init(200)
    yield
    pygame.quit()


@pytest.fixture
def renderer():
    proj = ScreenProjection(home_lat=50.0, home_lon=8.0, radius_km=50, screen_size=200)
    return RadarRenderer(200, proj, CLASSIC_AMBER)


class TestIsTracked:
    def test_matching_callsign_is_tracked(self, renderer):
        ac = Aircraft(icao_hex="abc", callsign="DLH400")
        assert renderer._is_tracked(ac, "DLH400") is True

    def test_case_insensitive_match(self, renderer):
        ac = Aircraft(icao_hex="abc", callsign="dlh400")
        assert renderer._is_tracked(ac, "DLH400") is True

    def test_whitespace_tolerant(self, renderer):
        ac = Aircraft(icao_hex="abc", callsign=" DLH400 ")
        assert renderer._is_tracked(ac, "DLH400") is True

    def test_different_callsign_not_tracked(self, renderer):
        ac = Aircraft(icao_hex="abc", callsign="SWR100")
        assert renderer._is_tracked(ac, "DLH400") is False

    def test_no_tracked_callsign_set(self, renderer):
        ac = Aircraft(icao_hex="abc", callsign="DLH400")
        assert renderer._is_tracked(ac, "") is False

    def test_aircraft_with_no_callsign_never_matches(self, renderer):
        ac = Aircraft(icao_hex="abc", callsign=None)
        assert renderer._is_tracked(ac, "DLH400") is False


class TestTrackedAircraftGetsAccentColour:
    def test_tracked_aircraft_uses_selected_colour(self, renderer):
        ac = Aircraft(icao_hex="abc", callsign="DLH400", lat=50.01, lon=8.01)
        colour = renderer._flight_icon_color(ac, renderer._is_tracked(ac, "DLH400"))
        assert colour == renderer.theme.aircraft_selected

    def test_untracked_aircraft_uses_normal_colour(self, renderer):
        ac = Aircraft(icao_hex="abc", callsign="DLH400", lat=50.01, lon=8.01)
        colour = renderer._flight_icon_color(ac, renderer._is_tracked(ac, "SWR100"))
        assert colour == renderer.theme.aircraft_dot

    def test_draw_aircraft_accepts_tracked_callsign_without_crashing(self, renderer):
        surf = pygame.Surface((200, 200))
        ac = Aircraft(icao_hex="abc", callsign="DLH400", lat=50.01, lon=8.01)
        renderer.draw_aircraft(surf, [ac], tracked_callsign="DLH400")

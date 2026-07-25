"""Tests for the detail screen's "Track"/"Untrack" footer action
(Ausbaustufe 2, Schritt 5, 5.1: "Aus der Detailansicht ... im Footer")."""

import pygame
import pytest

from flugradar.data_sources.models import Aircraft
from flugradar.display import scaling
from flugradar.display.screens.detail import DetailScreen
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
    return DetailScreen(300, CLASSIC_AMBER)


class TestFooterButtons:
    def test_aircraft_with_callsign_gets_track_button(self, screen):
        ac = Aircraft(icao_hex="abc", callsign="DLH400")
        assert "track" in screen._footer_buttons(ac)

    def test_aircraft_without_callsign_has_no_track_button(self, screen):
        ac = Aircraft(icao_hex="abc", callsign=None)
        assert "track" not in screen._footer_buttons(ac)
        assert "untrack" not in screen._footer_buttons(ac)

    def test_none_aircraft_only_has_radar(self, screen):
        assert screen._footer_buttons(None) == ["radar"]

    def test_currently_tracked_flight_shows_untrack(self, screen):
        ac = Aircraft(icao_hex="abc", callsign="DLH400")
        screen.tracked_callsign = "DLH400"
        buttons = screen._footer_buttons(ac)
        assert "untrack" in buttons
        assert "track" not in buttons

    def test_tracked_callsign_match_is_case_insensitive(self, screen):
        ac = Aircraft(icao_hex="abc", callsign="dlh400")
        screen.tracked_callsign = "DLH400"
        assert "untrack" in screen._footer_buttons(ac)

    def test_different_tracked_flight_still_shows_track(self, screen):
        ac = Aircraft(icao_hex="abc", callsign="DLH400")
        screen.tracked_callsign = "SWR100"
        buttons = screen._footer_buttons(ac)
        assert "track" in buttons
        assert "untrack" not in buttons

    def test_multi_aircraft_list_adds_prev_next(self, screen):
        ac = Aircraft(icao_hex="abc", callsign="DLH400")
        screen._aircraft_list = [ac, Aircraft(icao_hex="def", callsign="SWR1")]
        buttons = screen._footer_buttons(ac)
        assert buttons == ["prev", "next", "track", "radar"]


class TestHandleTapReturnsTrackAction:
    def test_tapping_track_button_returns_track(self, screen):
        ac = Aircraft(icao_hex="abc", callsign="DLH400")
        screen.set_aircraft(ac)
        screen.set_aircraft_list([ac])
        surf = pygame.Surface((300, 300))
        screen.draw(surf)

        from flugradar.display import nav
        rects = nav.footer_button_rects(len(screen._footer_buttons(ac)))
        track_idx = screen._footer_buttons(ac).index("track")
        rect = rects[track_idx]

        result = screen.handle_tap(rect.centerx, rect.centery)
        assert result == "track"

    def test_tapping_untrack_button_returns_untrack(self, screen):
        ac = Aircraft(icao_hex="abc", callsign="DLH400")
        screen.set_aircraft(ac)
        screen.set_aircraft_list([ac])
        screen.tracked_callsign = "DLH400"
        surf = pygame.Surface((300, 300))
        screen.draw(surf)

        from flugradar.display import nav
        rects = nav.footer_button_rects(len(screen._footer_buttons(ac)))
        idx = screen._footer_buttons(ac).index("untrack")
        rect = rects[idx]

        result = screen.handle_tap(rect.centerx, rect.centery)
        assert result == "untrack"

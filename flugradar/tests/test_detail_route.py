"""Tests for the detail screen's origin/destination line layout.

Origin and destination should share one line ("City (CODE)  →  City
(CODE)") whenever it fits the available chord width, and only fall back
to the old one-endpoint-per-line layout when it genuinely doesn't --
not unconditionally, which is what it did before this fix."""

import pygame
import pytest

from flugradar.data_sources.models import Aircraft
from flugradar.display import scaling
from flugradar.display.screens import detail as detail_mod
from flugradar.display.screens.detail import DetailScreen
from flugradar.display.theme import CLASSIC_AMBER


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((720, 720))
    scaling.init(720)
    yield
    pygame.quit()


@pytest.fixture
def screen():
    s = DetailScreen(720, CLASSIC_AMBER)
    s._ensure_fonts()
    return s


@pytest.fixture
def surf():
    return pygame.Surface((720, 720))


def _one_line_height(screen) -> int:
    return screen._body_font.get_height() + 1


class TestRouteFitsOnOneLine:
    def test_short_codes_stay_on_a_single_line(self, screen, surf):
        ac = Aircraft(icao_hex="a", callsign="DLH1", origin="FRA", destination="MUC")
        y = screen._draw_route(surf, ac, 300, 0, 720, 1)
        assert y - 300 == _one_line_height(screen)

    def test_typical_intercontinental_route_still_fits(self, screen, surf):
        # a real, fairly long pairing (city names, not just 3-letter codes)
        ac = Aircraft(icao_hex="a", callsign="DLH400", origin="JFK", destination="LAX")
        y = screen._draw_route(surf, ac, 300, 0, 720, 1)
        assert y - 300 == _one_line_height(screen)


class TestRouteWrapsWhenTooLong:
    def test_falls_back_to_two_lines_when_it_does_not_fit(self, screen, surf, monkeypatch):
        monkeypatch.setattr(
            detail_mod, "format_route_endpoint",
            lambda code: f"An Implausibly Long City Name That Cannot Possibly Fit ({code})",
        )
        ac = Aircraft(icao_hex="a", callsign="DLH1", origin="FRA", destination="MUC")
        y = screen._draw_route(surf, ac, 300, 0, 720, 1)
        assert y - 300 == 2 * _one_line_height(screen)

    def test_two_line_fallback_shows_an_arrow_after_the_first_endpoint(self, screen, surf, monkeypatch):
        monkeypatch.setattr(
            detail_mod, "format_route_endpoint",
            lambda code: f"An Implausibly Long City Name That Cannot Possibly Fit ({code})",
        )
        rendered = []
        monkeypatch.setattr(
            detail_mod, "draw_center_text",
            lambda surface, text, y, font, color: (rendered.append(text), y + font.get_height() + 1)[1],
        )
        ac = Aircraft(icao_hex="a", callsign="DLH1", origin="FRA", destination="MUC")
        screen._draw_route(surf, ac, 300, 0, 720, 1)
        assert len(rendered) == 2
        assert rendered[0].endswith("→")
        assert "→" not in rendered[1]


class TestSingleEndpointUnaffected:
    def test_origin_only_is_a_single_row_from_header(self, screen):
        ac = Aircraft(icao_hex="a", callsign="DLH1", origin="FRA", destination=None)
        rows = screen._build_header_rows(ac)
        route_rows = [r for r in rows if "FRA" in r[0]]
        assert len(route_rows) == 1
        assert route_rows[0][0].startswith("Von ")

    def test_destination_only_is_a_single_row_from_header(self, screen):
        ac = Aircraft(icao_hex="a", callsign="DLH1", origin=None, destination="MUC")
        rows = screen._build_header_rows(ac)
        route_rows = [r for r in rows if "MUC" in r[0]]
        assert len(route_rows) == 1
        assert route_rows[0][0].startswith("Nach ")

    def test_neither_known_adds_no_route_row(self, screen):
        ac = Aircraft(icao_hex="a", callsign="DLH1", origin=None, destination=None)
        rows = screen._build_header_rows(ac)
        assert len(rows) == 1  # just the flight-id title row

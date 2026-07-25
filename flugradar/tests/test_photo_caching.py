"""Tests that DetailScreen/TrackedFlightScreen decode a photo at most once
per path instead of re-decoding+rescaling+masking it every frame.

Regression coverage for a real perf issue found in the Pi4 performance
audit: draw() runs every frame, but load_photo_surface() re-reads and
re-processes the JPEG from disk unconditionally -- expensive and entirely
avoidable for a photo that doesn't change frame to frame.
"""
from unittest.mock import MagicMock, patch

import pygame
import pytest

from flugradar.data_sources.models import Aircraft
from flugradar.display import scaling
from flugradar.display.screens.detail import DetailScreen
from flugradar.display.screens.tracking import TrackedFlightScreen
from flugradar.display.theme import CLASSIC_AMBER


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((300, 300))
    scaling.init(300)
    yield
    pygame.quit()


@pytest.fixture
def surf():
    return pygame.Surface((300, 300))


def _fake_photo():
    s = pygame.Surface((20, 20))
    return s


class TestDetailScreenPhotoCache:
    def test_decodes_once_across_repeated_frames(self, surf):
        screen = DetailScreen(300, CLASSIC_AMBER)
        ac = Aircraft(icao_hex="abc123", callsign="DLH400")
        screen.set_aircraft(ac)
        screen.set_aircraft_list([ac])

        with patch(
            "flugradar.display.screens.detail.get_photo_info",
            return_value={"path": "/fake/abc123.jpg", "credit": ""},
        ), patch(
            "flugradar.display.screens.detail.load_photo_surface",
            return_value=_fake_photo(),
        ) as mock_load:
            for _ in range(5):
                screen.draw(surf)

        mock_load.assert_called_once()

    def test_redecodes_when_photo_path_changes(self, surf):
        screen = DetailScreen(300, CLASSIC_AMBER)
        ac = Aircraft(icao_hex="abc123", callsign="DLH400")
        screen.set_aircraft(ac)
        screen.set_aircraft_list([ac])

        with patch(
            "flugradar.display.screens.detail.get_photo_info",
            side_effect=[
                {"path": "/fake/a.jpg", "credit": ""},
                {"path": "/fake/b.jpg", "credit": ""},
            ],
        ), patch(
            "flugradar.display.screens.detail.load_photo_surface",
            return_value=_fake_photo(),
        ) as mock_load:
            screen.draw(surf)
            screen.draw(surf)

        assert mock_load.call_count == 2

    def test_no_photo_does_not_touch_loader(self, surf):
        screen = DetailScreen(300, CLASSIC_AMBER)
        ac = Aircraft(icao_hex="abc123", callsign="DLH400")
        screen.set_aircraft(ac)
        screen.set_aircraft_list([ac])

        with patch(
            "flugradar.display.screens.detail.get_photo_info", return_value=None,
        ), patch(
            "flugradar.display.screens.detail.load_photo_surface",
        ) as mock_load:
            screen.draw(surf)

        mock_load.assert_not_called()


class TestTrackedFlightScreenPhotoCache:
    def test_decodes_once_across_repeated_frames(self, surf):
        screen = TrackedFlightScreen(300, CLASSIC_AMBER)
        ac = Aircraft(icao_hex="abc123", callsign="DLH400", lat=50.0, lon=8.0)
        screen.set_tracking(ac, True, None)

        with patch(
            "flugradar.display.screens.tracking.get_photo_info",
            return_value={"path": "/fake/abc123.jpg", "credit": ""},
        ), patch(
            "flugradar.display.screens.tracking.load_photo_surface",
            return_value=_fake_photo(),
        ) as mock_load:
            for _ in range(5):
                screen.draw(surf)

        mock_load.assert_called_once()

    def test_redecodes_for_a_newly_tracked_flight_with_a_different_photo(self, surf):
        screen = TrackedFlightScreen(300, CLASSIC_AMBER)
        ac1 = Aircraft(icao_hex="abc123", callsign="DLH400", lat=50.0, lon=8.0)
        ac2 = Aircraft(icao_hex="def456", callsign="SWR100", lat=50.0, lon=8.0)

        with patch(
            "flugradar.display.screens.tracking.get_photo_info",
            side_effect=[
                {"path": "/fake/a.jpg", "credit": ""},
                {"path": "/fake/b.jpg", "credit": ""},
            ],
        ), patch(
            "flugradar.display.screens.tracking.load_photo_surface",
            return_value=_fake_photo(),
        ) as mock_load:
            screen.set_tracking(ac1, True, None)
            screen.draw(surf)
            screen.set_tracking(ac2, True, None)
            screen.draw(surf)

        assert mock_load.call_count == 2

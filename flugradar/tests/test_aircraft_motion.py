"""Unit tests for RadarRenderer's aircraft position glide.

New ADS-B data arrives in discrete polls; without smoothing an aircraft's
screen icon would teleport to the new lat/lon the instant a poll lands.
These tests exercise the interpolation state machine directly (no pygame
surfaces involved) with a controlled fake clock.
"""

import pygame
import pytest

from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.projection import ScreenProjection
from flugradar.display import scaling
from flugradar.display.renderer import RadarRenderer
from flugradar.display.theme import CLASSIC_AMBER


def _aircraft(lat, lon, hex_="abc123"):
    return Aircraft(icao_hex=hex_, lat=lat, lon=lon, callsign="TEST1")


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def renderer():
    scaling.init(200)
    proj = ScreenProjection(home_lat=50.0, home_lon=8.0, radius_km=50, screen_size=200)
    return RadarRenderer(200, proj, CLASSIC_AMBER)


class TestMotionState:
    def test_first_sighting_places_immediately_no_glide(self, renderer):
        lat, lon = renderer._update_motion(_aircraft(50.01, 8.01), now=100.0)
        assert (lat, lon) == (50.01, 8.01)
        assert renderer._motion["abc123"]["move_dur"] == 0.0

    def test_position_change_starts_a_glide_not_a_jump(self, renderer):
        renderer._update_motion(_aircraft(50.01, 8.01), now=100.0)
        # second poll 3s later with a new position
        lat, lon = renderer._update_motion(_aircraft(50.02, 8.02), now=103.0)
        # immediately after the change, display position must not have
        # jumped straight to the new target
        assert (lat, lon) != (50.02, 8.02)
        assert lat == pytest.approx(50.01, abs=1e-6)

    def test_glide_reaches_target_after_its_duration(self, renderer):
        renderer._update_motion(_aircraft(50.01, 8.01), now=100.0)
        renderer._update_motion(_aircraft(50.02, 8.02), now=103.0)
        m = renderer._motion["abc123"]
        lat, lon = renderer._interpolated_position(m, now=103.0 + m["move_dur"])
        assert (lat, lon) == pytest.approx((50.02, 8.02))

    def test_glide_duration_adapts_to_observed_poll_interval(self, renderer):
        renderer._update_motion(_aircraft(50.01, 8.01), now=100.0)
        renderer._update_motion(_aircraft(50.02, 8.02), now=105.0)
        assert renderer._motion["abc123"]["move_dur"] == pytest.approx(5.0)

    def test_glide_duration_is_clamped(self, renderer):
        renderer._update_motion(_aircraft(50.01, 8.01), now=100.0)
        # absurdly short and absurdly long gaps both get clamped to a sane range
        renderer._update_motion(_aircraft(50.02, 8.02), now=100.05)
        assert renderer._motion["abc123"]["move_dur"] == pytest.approx(0.2)

        renderer._update_motion(_aircraft(50.03, 8.03), now=1000.0)
        assert renderer._motion["abc123"]["move_dur"] == pytest.approx(10.0)

    def test_interrupted_glide_resumes_from_current_position_not_old_target(self, renderer):
        renderer._update_motion(_aircraft(50.00, 8.00), now=100.0)
        renderer._update_motion(_aircraft(50.10, 8.10), now=105.0)  # 5s glide towards 50.10
        # a new poll lands mid-glide, 1s in (20% through a 5s glide)
        mid_lat, _ = renderer._update_motion(_aircraft(50.20, 8.20), now=106.0)
        m = renderer._motion["abc123"]
        # the new glide's start point must be roughly where we actually were
        # displayed (partway to 50.10), not the original 50.00 nor 50.10
        assert m["start_lat"] == pytest.approx(mid_lat)
        assert 50.00 < m["start_lat"] < 50.10

    def test_stationary_aircraft_does_not_restart_glide(self, renderer):
        renderer._update_motion(_aircraft(50.01, 8.01), now=100.0)
        renderer._update_motion(_aircraft(50.02, 8.02), now=103.0)
        m_before = dict(renderer._motion["abc123"])
        # same position reported again next poll -- no new glide should start
        renderer._update_motion(_aircraft(50.02, 8.02), now=106.0)
        assert renderer._motion["abc123"]["move_start"] == m_before["move_start"]

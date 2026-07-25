"""RadarApp's tracked-flight lifecycle (Ausbaustufe 2, Schritt 5): starting
tracking, ending it on landing, ending it on timeout, and NOT ending it
just because the aircraft happens to be on the ground before takeoff."""

import pygame
import pytest

from flugradar.config import settings as settings_mod
from flugradar.config.settings import AppSettings
from flugradar.data_sources.models import Aircraft
from flugradar.display.app import ActiveScreen, RadarApp


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((200, 200))
    from flugradar.display import scaling
    scaling.init(200)
    yield
    pygame.quit()


@pytest.fixture
def settings(tmp_path, monkeypatch):
    portal_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
    s = AppSettings()
    s.tracking_timeout_s = 900
    return s


@pytest.fixture
def app(settings):
    return RadarApp(settings, screen_size=200, demo_mode=True)


class TestStartTracking:
    def test_persists_callsign_and_resets_lifecycle_state(self, app, settings):
        app._start_tracking("DLH400")
        assert settings.tracked_callsign == "DLH400"
        assert app._tracked_last_seen is not None
        assert app._tracked_was_airborne is False
        assert app._tracked_last_snapshot is None

    def test_survives_a_simulated_restart(self, settings):
        settings.save_portal_settings({"tracked_callsign": "DLH400"})
        reloaded = AppSettings()
        assert reloaded.tracked_callsign == "DLH400"


class TestLandingEndsTracking:
    def test_landing_after_being_airborne_ends_tracking(self, app, settings):
        ac = Aircraft(icao_hex="a", callsign="DLH400", lat=50.0, lon=8.0, is_on_ground=False)
        app._aircraft = [ac]
        app._start_tracking("DLH400")
        app._active = ActiveScreen.TRACKING

        app._update_tracking_lifecycle(now=1000.0)  # airborne poll
        assert app._tracked_was_airborne is True

        ac.is_on_ground = True
        app._update_tracking_lifecycle(now=1010.0)  # landed poll

        assert settings.tracked_callsign == ""
        assert app._active == ActiveScreen.RADAR

    def test_ground_before_ever_airborne_does_not_end_tracking(self, app, settings):
        # e.g. tracking started while the flight is still at the gate
        ac = Aircraft(icao_hex="a", callsign="RYR1", lat=50.0, lon=8.0, is_on_ground=True)
        app._aircraft = [ac]
        app._start_tracking("RYR1")
        app._active = ActiveScreen.TRACKING

        app._update_tracking_lifecycle(now=1000.0)

        assert settings.tracked_callsign == "RYR1"
        assert app._active == ActiveScreen.TRACKING


class TestTimeoutEndsTracking:
    def test_no_reception_for_the_full_timeout_ends_tracking(self, app, settings):
        app._aircraft = []
        app._start_tracking("SWR100")
        app._active = ActiveScreen.TRACKING
        app._tracked_last_seen = 0.0  # long ago

        app._update_tracking_lifecycle(now=settings.tracking_timeout_s + 1.0)

        assert settings.tracked_callsign == ""
        assert app._active == ActiveScreen.RADAR

    def test_reception_within_timeout_keeps_tracking(self, app, settings):
        ac = Aircraft(icao_hex="a", callsign="SWR100", lat=50.0, lon=8.0)
        app._aircraft = [ac]
        app._start_tracking("SWR100")
        app._active = ActiveScreen.TRACKING

        app._update_tracking_lifecycle(now=settings.tracking_timeout_s - 1.0)

        assert settings.tracked_callsign == "SWR100"
        assert app._active == ActiveScreen.TRACKING

    def test_ending_tracking_while_on_a_different_screen_does_not_change_active_screen(
        self, app, settings,
    ):
        app._aircraft = []
        app._start_tracking("SWR100")
        app._active = ActiveScreen.CLOCK
        app._tracked_last_seen = 0.0

        app._update_tracking_lifecycle(now=settings.tracking_timeout_s + 1.0)

        assert settings.tracked_callsign == ""
        assert app._active == ActiveScreen.CLOCK  # untouched, not forced to RADAR


class TestFindTrackedAircraft:
    def test_finds_matching_callsign_case_insensitively(self, app, settings):
        ac = Aircraft(icao_hex="a", callsign="dlh400")
        app._aircraft = [ac]
        settings.tracked_callsign = "DLH400"
        assert app._find_tracked_aircraft() is ac

    def test_returns_none_when_nothing_tracked(self, app, settings):
        app._aircraft = [Aircraft(icao_hex="a", callsign="DLH400")]
        settings.tracked_callsign = ""
        assert app._find_tracked_aircraft() is None

    def test_returns_none_when_tracked_flight_not_in_range(self, app, settings):
        app._aircraft = [Aircraft(icao_hex="a", callsign="OTHER")]
        settings.tracked_callsign = "DLH400"
        assert app._find_tracked_aircraft() is None


class TestUpdateTrackingScreen:
    def test_current_aircraft_marked_as_current(self, app, settings):
        ac = Aircraft(icao_hex="a", callsign="DLH400", lat=50.0, lon=8.0)
        app._aircraft = [ac]
        settings.tracked_callsign = "DLH400"

        class _Fake:
            def set_tracking(self, aircraft, is_current, last_seen_ago_s):
                self.aircraft, self.is_current, self.last_seen_ago_s = aircraft, is_current, last_seen_ago_s

        fake = _Fake()
        app._update_tracking_screen(fake)
        assert fake.aircraft is ac
        assert fake.is_current is True
        assert fake.last_seen_ago_s is None

    def test_out_of_range_uses_last_snapshot_with_age(self, app, settings):
        ac = Aircraft(icao_hex="a", callsign="DLH400", lat=50.0, lon=8.0)
        app._aircraft = [ac]
        settings.tracked_callsign = "DLH400"
        app._update_tracking_lifecycle(now=1000.0)  # populates the snapshot

        app._aircraft = []  # now out of range
        app._tracked_last_seen = 1000.0

        class _Fake:
            def set_tracking(self, aircraft, is_current, last_seen_ago_s):
                self.aircraft, self.is_current, self.last_seen_ago_s = aircraft, is_current, last_seen_ago_s

        fake = _Fake()
        import time
        real_monotonic = time.monotonic
        try:
            time.monotonic = lambda: 1030.0
            app._update_tracking_screen(fake)
        finally:
            time.monotonic = real_monotonic

        assert fake.aircraft is ac
        assert fake.is_current is False
        assert fake.last_seen_ago_s == pytest.approx(30.0)

    def test_nothing_tracked_passes_none(self, app, settings):
        settings.tracked_callsign = ""

        class _Fake:
            def set_tracking(self, aircraft, is_current, last_seen_ago_s):
                self.aircraft = aircraft

        fake = _Fake()
        app._update_tracking_screen(fake)
        assert fake.aircraft is None

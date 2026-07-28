"""Tests for the WLAN setup watchdog (flugradar/system/network_watchdog.py).

All nmcli calls go through `_run_nmcli`, which is monkeypatched here to a
scripted fake -- no real subprocess/nmcli/sudo call ever runs.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from flugradar.system import network_watchdog as watchdog_mod
from flugradar.system.network_watchdog import (
    NetworkWatchdog,
    SetupState,
    WatchdogConfig,
    active_connection_name,
    has_known_wifi_profiles,
    is_client_connected,
    scan_networks,
)


def _cp(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture(autouse=True)
def status_file(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog_mod, "STATUS_FILE", tmp_path / "network_status.json")
    monkeypatch.setattr(watchdog_mod, "FORCE_SETUP_FILE", tmp_path / "network_force_setup.flag")
    monkeypatch.setattr(watchdog_mod, "CANCEL_SETUP_FILE", tmp_path / "network_cancel_setup.flag")
    return tmp_path / "network_status.json"


class FakeClock:
    """Controllable stand-in for time.monotonic()."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(watchdog_mod.time, "monotonic", fake)
    return fake


def _config(**overrides) -> WatchdogConfig:
    defaults = dict(
        boot_grace_s=45.0, outage_tolerance_s=300.0,
        hotspot_ssid="SassoRadar-Setup", hotspot_password="testpass1",
        interface="wlan0",
    )
    defaults.update(overrides)
    return WatchdogConfig(**defaults)


class TestWatchdogConfig:
    def test_defaults(self):
        cfg = WatchdogConfig()
        assert cfg.boot_grace_s == 45.0
        assert cfg.outage_tolerance_s == 300.0
        assert len(cfg.hotspot_password) >= 8

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("WIFI_BOOT_GRACE_S", "10")
        monkeypatch.setenv("WIFI_OUTAGE_TOLERANCE_S", "60")
        monkeypatch.setenv("WIFI_HOTSPOT_SSID", "TestHotspot")
        monkeypatch.setenv("WIFI_HOTSPOT_PASSWORD", "fixedpass")
        cfg = WatchdogConfig.from_env()
        assert cfg.boot_grace_s == 10.0
        assert cfg.outage_tolerance_s == 60.0
        assert cfg.hotspot_ssid == "TestHotspot"
        assert cfg.hotspot_password == "fixedpass"

    def test_empty_password_is_auto_generated(self, monkeypatch):
        monkeypatch.delenv("WIFI_HOTSPOT_PASSWORD", raising=False)
        cfg = WatchdogConfig.from_env()
        assert len(cfg.hotspot_password) >= 8


class TestNmcliParsing:
    def test_active_connection_name_parses_profile(self):
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, "GENERAL.CONNECTION:HomeWifi\n")):
            assert active_connection_name() == "HomeWifi"

    def test_active_connection_name_none_when_disconnected(self):
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, "GENERAL.CONNECTION:--\n")):
            assert active_connection_name() is None

    def test_is_client_connected_true_for_real_network(self):
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, "GENERAL.CONNECTION:HomeWifi\n")):
            assert is_client_connected() is True

    def test_is_client_connected_false_for_own_hotspot(self):
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, "GENERAL.CONNECTION:SassoRadarSetup\n")):
            assert is_client_connected() is False

    def test_has_known_wifi_profiles_true(self):
        out = "HomeWifi:802-11-wireless\nWired connection 1:802-3-ethernet\n"
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, out)):
            assert has_known_wifi_profiles() is True

    def test_has_known_wifi_profiles_false_when_only_hotspot(self):
        out = "SassoRadarSetup:802-11-wireless\nWired connection 1:802-3-ethernet\n"
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, out)):
            assert has_known_wifi_profiles() is False

    def test_has_known_wifi_profiles_false_when_empty(self):
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, "")):
            assert has_known_wifi_profiles() is False

    def test_scan_networks_sorted_and_deduped(self):
        list_out = (
            "WeakWifi:30:WPA2\n"
            "StrongWifi:80:WPA2\n"
            "StrongWifi:80:WPA2\n"  # duplicate BSSID for the same SSID
            "OpenWifi:50:\n"
        )

        def fake(args, timeout=None):
            if "rescan" in args:
                return _cp(0)
            return _cp(0, list_out)

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            networks = scan_networks()

        assert [n["ssid"] for n in networks] == ["StrongWifi", "OpenWifi", "WeakWifi"]
        assert networks[0]["secured"] is True
        assert networks[1]["secured"] is False

    def test_scan_networks_excludes_nothing_on_failure(self):
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(1, "", "no wifi device")):
            assert scan_networks() == []


class TestConnectToWifi:
    def test_success(self):
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, "Device 'wlan0' successfully activated")):
            ok, detail = watchdog_mod.connect_to_wifi("HomeWifi", "secret")
        assert ok is True

    def test_failure_reports_stderr(self):
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(1, "", "Secrets were required, but not provided")):
            ok, detail = watchdog_mod.connect_to_wifi("HomeWifi", "wrong")
        assert ok is False
        assert "Secrets" in detail


class TestNetworkWatchdogStateMachine:
    def test_boot_grace_waits_when_known_profile_exists(self, clock):
        cfg = _config(boot_grace_s=45.0)
        with patch.object(watchdog_mod, "_run_nmcli") as mock_run:
            mock_run.side_effect = lambda args, timeout=None: (
                _cp(0, "GENERAL.CONNECTION:--\n") if "device" in args and "show" in args
                else _cp(0, "HomeWifi:802-11-wireless\n")
            )
            wd = NetworkWatchdog(cfg)
            clock.advance(10)  # well within the 45s grace window
            wd.tick()
        assert wd._state == SetupState.GRACE
        status = json.loads(watchdog_mod.STATUS_FILE.read_text())
        assert status["state"] == SetupState.GRACE

    def test_boot_grace_enters_setup_mode_after_timeout(self, clock):
        cfg = _config(boot_grace_s=45.0)
        hotspot_calls = []

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:--\n")
            if "hotspot" in args:
                hotspot_calls.append(args)
                return _cp(0)
            return _cp(0, "HomeWifi:802-11-wireless\n")

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            clock.advance(46)  # past the grace window
            wd.tick()

        assert wd._state == SetupState.SETUP_MODE
        assert len(hotspot_calls) == 1
        status = json.loads(watchdog_mod.STATUS_FILE.read_text())
        assert status["state"] == SetupState.SETUP_MODE
        assert status["hotspot_ssid"] == cfg.hotspot_ssid

    def test_brand_new_device_skips_grace_period_entirely(self, clock):
        """No saved wifi profile at all -- must not wait out the full
        boot grace window, or a genuinely new device sits blank for
        45s+ before showing any setup instructions."""
        cfg = _config(boot_grace_s=45.0)

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:--\n")
            if "hotspot" in args:
                return _cp(0)
            return _cp(0, "")  # no connection profiles saved at all

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            clock.advance(1)  # barely any time has passed
            wd.tick()

        assert wd._state == SetupState.SETUP_MODE

    def test_outage_tolerated_within_window(self, clock):
        cfg = _config(outage_tolerance_s=300.0)
        connected = {"value": True}

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:HomeWifi\n" if connected["value"] else "GENERAL.CONNECTION:--\n")
            return _cp(0, "HomeWifi:802-11-wireless\n")

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            wd.tick()  # establishes CONNECTED
            assert wd._state == SetupState.CONNECTED

            connected["value"] = False
            clock.advance(1)
            wd.tick()  # drop -> OUTAGE
            assert wd._state == SetupState.OUTAGE

            clock.advance(100)  # well within the 300s tolerance
            wd.tick()
            assert wd._state == SetupState.OUTAGE

            connected["value"] = True
            wd.tick()  # reconnects -> back to CONNECTED, no setup mode
            assert wd._state == SetupState.CONNECTED

    def test_outage_exceeding_tolerance_enters_setup_mode(self, clock):
        cfg = _config(outage_tolerance_s=300.0)
        connected = {"value": True}
        hotspot_calls = []

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:HomeWifi\n" if connected["value"] else "GENERAL.CONNECTION:--\n")
            if "hotspot" in args:
                hotspot_calls.append(args)
                return _cp(0)
            return _cp(0, "HomeWifi:802-11-wireless\n")

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            wd.tick()
            assert wd._state == SetupState.CONNECTED

            connected["value"] = False
            clock.advance(1)
            wd.tick()
            assert wd._state == SetupState.OUTAGE

            clock.advance(301)  # past the 300s tolerance
            wd.tick()

        assert wd._state == SetupState.SETUP_MODE
        assert len(hotspot_calls) == 1

    def test_setup_mode_exits_once_a_connection_appears(self, clock):
        cfg = _config()
        connected = {"value": False}

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:HomeWifi\n" if connected["value"] else "GENERAL.CONNECTION:--\n")
            if "hotspot" in args:
                return _cp(0)
            return _cp(0, "")

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            wd.tick()
            assert wd._state == SetupState.SETUP_MODE

            connected["value"] = True
            wd.tick()

        assert wd._state == SetupState.CONNECTED
        status = json.loads(watchdog_mod.STATUS_FILE.read_text())
        assert status["state"] == SetupState.CONNECTED
        assert status["connected_ssid"] == "HomeWifi"

    def test_tick_never_raises_on_nmcli_failure(self, clock):
        cfg = _config()
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(1, "", "nmcli: command not found")):
            wd = NetworkWatchdog(cfg)
            wd.tick()  # must not raise


class TestManualTriggers:
    """The device-menu "WLAN einrichten" action and its cancel-gesture
    counterpart run in a different process than the watchdog service, so
    they can't call methods on its live NetworkWatchdog instance --
    trigger_wifi_setup()/cancel_wifi_setup() act immediately themselves
    *and* leave a flag file for the watchdog's own next tick() to consume,
    so it doesn't fight the external change on its following cycle."""

    def test_trigger_wifi_setup_acts_immediately(self, clock):
        cfg = _config()
        hotspot_calls = []

        def fake(args, timeout=None):
            if "hotspot" in args:
                hotspot_calls.append(args)
                return _cp(0)
            return _cp(0, "")

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            watchdog_mod.trigger_wifi_setup(cfg)

        assert len(hotspot_calls) == 1
        status = json.loads(watchdog_mod.STATUS_FILE.read_text())
        assert status["state"] == SetupState.SETUP_MODE
        assert watchdog_mod.FORCE_SETUP_FILE.exists()

    def test_watchdog_tick_consumes_force_flag_without_fighting_it(self, clock):
        """A manual trigger happens between two watchdog ticks -- the
        watchdog still thinks it's CONNECTED (stale, from its own last
        tick) and would otherwise treat the now-down connection as an
        OUTAGE. The flag must make it sync to SETUP_MODE instead."""
        cfg = _config()
        hotspot_calls = []

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:HomeWifi\n")
            if "hotspot" in args:
                hotspot_calls.append(args)
                return _cp(0)
            return _cp(0, "HomeWifi:802-11-wireless\n")

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            wd.tick()
            assert wd._state == SetupState.CONNECTED

        # external trigger, as if from a different process
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0)):
            watchdog_mod.trigger_wifi_setup(cfg)
        assert watchdog_mod.FORCE_SETUP_FILE.exists()

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            wd.tick()  # watchdog's own next cycle, still thinks CONNECTED

        assert wd._state == SetupState.SETUP_MODE
        assert not watchdog_mod.FORCE_SETUP_FILE.exists()

    def test_cancel_wifi_setup_acts_immediately(self, clock):
        cfg = _config()

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:--\n")
            return _cp(0, "")

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            watchdog_mod.cancel_wifi_setup(cfg)

        status = json.loads(watchdog_mod.STATUS_FILE.read_text())
        assert status["state"] == SetupState.GRACE
        assert watchdog_mod.CANCEL_SETUP_FILE.exists()

    def test_watchdog_tick_consumes_cancel_flag(self, clock):
        cfg = _config()

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:SassoRadarSetup\n")
            return _cp(0, "")

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            wd._state = SetupState.SETUP_MODE

        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0)):
            watchdog_mod.cancel_wifi_setup(cfg)
        assert watchdog_mod.CANCEL_SETUP_FILE.exists()

        with patch.object(watchdog_mod, "_run_nmcli", side_effect=fake) as mock_run:
            wd.tick()

        assert wd._state == SetupState.GRACE
        assert not watchdog_mod.CANCEL_SETUP_FILE.exists()
        # the pending FORCE flag (if any) is also cleared by a cancel
        assert not watchdog_mod.FORCE_SETUP_FILE.exists()
        stop_calls = [c for c in mock_run.call_args_list if "down" in c.args[0]]
        assert len(stop_calls) == 1


class TestReadStatus:
    def test_read_status_none_when_missing(self):
        assert watchdog_mod.read_status() is None

    def test_read_status_none_on_corrupt_json(self):
        watchdog_mod.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        watchdog_mod.STATUS_FILE.write_text("{not json")
        assert watchdog_mod.read_status() is None

    def test_read_status_roundtrip(self, clock):
        cfg = _config()
        with patch.object(watchdog_mod, "_run_nmcli", return_value=_cp(0, "")):
            NetworkWatchdog(cfg)
        status = watchdog_mod.read_status()
        assert status["state"] == SetupState.GRACE
        assert status["hotspot_ssid"] == cfg.hotspot_ssid

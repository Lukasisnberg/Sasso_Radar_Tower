"""Tests for the WLAN backend (flugradar/system/network.py).

All nmcli calls go through `_run_nmcli`, which is monkeypatched here to a
scripted fake -- no real subprocess/nmcli/sudo call ever runs, and no real
network connection is ever touched.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from flugradar.system import network as network_mod
from flugradar.system.network import (
    ConnectResult,
    NetworkInfo,
    NetworkWatchdog,
    SetupState,
    WatchdogConfig,
    active_connection_name,
    connect,
    has_known_wifi_profiles,
    is_client_connected,
    scan_networks,
)


def _cp(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture(autouse=True)
def status_file(tmp_path, monkeypatch):
    monkeypatch.setattr(network_mod, "STATUS_FILE", tmp_path / "network_status.json")
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
    monkeypatch.setattr(network_mod.time, "monotonic", fake)
    return fake


def _config(**overrides) -> WatchdogConfig:
    defaults = dict(boot_grace_s=45.0, outage_tolerance_s=300.0, interface="wlan0")
    defaults.update(overrides)
    return WatchdogConfig(**defaults)


class TestWatchdogConfig:
    def test_defaults(self):
        cfg = WatchdogConfig()
        assert cfg.boot_grace_s == 45.0
        assert cfg.outage_tolerance_s == 300.0
        assert cfg.interface == "wlan0"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("WIFI_BOOT_GRACE_S", "10")
        monkeypatch.setenv("WIFI_OUTAGE_TOLERANCE_S", "60")
        monkeypatch.setenv("WIFI_INTERFACE", "wlan1")
        cfg = WatchdogConfig.from_env()
        assert cfg.boot_grace_s == 10.0
        assert cfg.outage_tolerance_s == 60.0
        assert cfg.interface == "wlan1"


class TestNmcliParsing:
    def test_active_connection_name_parses_profile(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(0, "GENERAL.CONNECTION:HomeWifi\n")):
            assert active_connection_name() == "HomeWifi"

    def test_active_connection_name_none_when_disconnected(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(0, "GENERAL.CONNECTION:--\n")):
            assert active_connection_name() is None

    def test_is_client_connected_true(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(0, "GENERAL.CONNECTION:HomeWifi\n")):
            assert is_client_connected() is True

    def test_is_client_connected_false(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(0, "GENERAL.CONNECTION:--\n")):
            assert is_client_connected() is False

    def test_has_known_wifi_profiles_true(self):
        out = "HomeWifi:802-11-wireless\nWired connection 1:802-3-ethernet\n"
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(0, out)):
            assert has_known_wifi_profiles() is True

    def test_has_known_wifi_profiles_false(self):
        out = "Wired connection 1:802-3-ethernet\n"
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(0, out)):
            assert has_known_wifi_profiles() is False


class TestScanNetworks:
    def test_sorted_strongest_first(self):
        list_out = "WeakWifi:30:WPA2\nStrongWifi:80:WPA2\nOpenWifi:50:\n"

        def fake(args, timeout=None):
            if "rescan" in args:
                return _cp(0)
            return _cp(0, list_out)

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
            networks = scan_networks()

        assert [n.ssid for n in networks] == ["StrongWifi", "OpenWifi", "WeakWifi"]
        assert networks[0].secured is True
        assert networks[1].secured is False

    def test_duplicate_ssid_collapses_to_strongest(self):
        # Same SSID seen from two access points -- the weaker one must not
        # produce a second row.
        list_out = "HomeWifi:40:WPA2\nHomeWifi:75:WPA2\n"

        def fake(args, timeout=None):
            if "rescan" in args:
                return _cp(0)
            return _cp(0, list_out)

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
            networks = scan_networks()

        assert len(networks) == 1
        assert networks[0].signal == 75

    def test_marks_current_connection(self):
        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:HomeWifi\n")
            if "rescan" in args:
                return _cp(0)
            return _cp(0, "HomeWifi:80:WPA2\nOtherWifi:50:\n")

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
            networks = scan_networks()

        by_ssid = {n.ssid: n for n in networks}
        assert by_ssid["HomeWifi"].is_current is True
        assert by_ssid["OtherWifi"].is_current is False

    def test_returns_empty_list_on_failure(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(1, "", "no wifi device")):
            assert scan_networks() == []


class TestConnect:
    def test_success(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(0, "Device 'wlan0' successfully activated")):
            result = connect("HomeWifi", "secret")
        assert result.ok is True
        assert result.error is None

    def test_wrong_password(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(1, "", "Secrets were required, but not provided")):
            result = connect("HomeWifi", "wrong")
        assert result.ok is False
        assert result.error == "wrong_password"

    def test_out_of_range(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(1, "", "Error: No network with SSID 'HomeWifi' found.")):
            result = connect("HomeWifi", "secret")
        assert result.ok is False
        assert result.error == "out_of_range"

    def test_timeout(self):
        import subprocess
        with patch.object(network_mod, "_run_nmcli", side_effect=subprocess.TimeoutExpired(cmd="nmcli", timeout=45)):
            result = connect("HomeWifi", "secret")
        assert result.ok is False
        assert result.error == "timeout"

    def test_unknown_failure(self):
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(1, "", "something unexpected")):
            result = connect("HomeWifi", "secret")
        assert result.ok is False
        assert result.error == "unknown"

    def test_open_network_no_password_arg(self):
        captured = {}

        def fake(args, timeout=None):
            captured["args"] = args
            return _cp(0)

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
            connect("OpenWifi", None)
        assert "password" not in captured["args"]


class TestNetworkWatchdogStateMachine:
    def test_boot_grace_waits_when_known_profile_exists(self, clock):
        cfg = _config(boot_grace_s=45.0)
        with patch.object(network_mod, "_run_nmcli") as mock_run:
            mock_run.side_effect = lambda args, timeout=None: (
                _cp(0, "GENERAL.CONNECTION:--\n") if "device" in args and "show" in args
                else _cp(0, "HomeWifi:802-11-wireless\n")
            )
            wd = NetworkWatchdog(cfg)
            clock.advance(10)  # well within the 45s grace window
            wd.tick()
        assert wd._state == SetupState.GRACE
        status = json.loads(network_mod.STATUS_FILE.read_text())
        assert status["state"] == SetupState.GRACE

    def test_boot_grace_needs_wifi_after_timeout(self, clock):
        cfg = _config(boot_grace_s=45.0)

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:--\n")
            return _cp(0, "HomeWifi:802-11-wireless\n")

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            clock.advance(46)  # past the grace window
            wd.tick()

        assert wd._state == SetupState.NEEDS_WIFI
        status = json.loads(network_mod.STATUS_FILE.read_text())
        assert status["state"] == SetupState.NEEDS_WIFI

    def test_brand_new_device_skips_grace_period_entirely(self, clock):
        """No saved wifi profile at all -- must not wait out the full
        boot grace window, or a genuinely new device sits blank for
        45s+ before showing any setup instructions."""
        cfg = _config(boot_grace_s=45.0)

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:--\n")
            return _cp(0, "")  # no connection profiles saved at all

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            clock.advance(1)  # barely any time has passed
            wd.tick()

        assert wd._state == SetupState.NEEDS_WIFI

    def test_outage_tolerated_within_window(self, clock):
        cfg = _config(outage_tolerance_s=300.0)
        connected = {"value": True}

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:HomeWifi\n" if connected["value"] else "GENERAL.CONNECTION:--\n")
            return _cp(0, "HomeWifi:802-11-wireless\n")

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
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
            wd.tick()  # reconnects -> back to CONNECTED
            assert wd._state == SetupState.CONNECTED

    def test_outage_exceeding_tolerance_needs_wifi(self, clock):
        cfg = _config(outage_tolerance_s=300.0)
        connected = {"value": True}

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:HomeWifi\n" if connected["value"] else "GENERAL.CONNECTION:--\n")
            return _cp(0, "HomeWifi:802-11-wireless\n")

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            wd.tick()
            assert wd._state == SetupState.CONNECTED

            connected["value"] = False
            clock.advance(1)
            wd.tick()
            assert wd._state == SetupState.OUTAGE

            clock.advance(301)  # past the 300s tolerance
            wd.tick()

        assert wd._state == SetupState.NEEDS_WIFI

    def test_needs_wifi_exits_once_a_connection_appears(self, clock):
        cfg = _config()
        connected = {"value": False}

        def fake(args, timeout=None):
            if "device" in args and "show" in args:
                return _cp(0, "GENERAL.CONNECTION:HomeWifi\n" if connected["value"] else "GENERAL.CONNECTION:--\n")
            return _cp(0, "")

        with patch.object(network_mod, "_run_nmcli", side_effect=fake):
            wd = NetworkWatchdog(cfg)
            wd.tick()
            assert wd._state == SetupState.NEEDS_WIFI

            connected["value"] = True
            wd.tick()

        assert wd._state == SetupState.CONNECTED
        status = json.loads(network_mod.STATUS_FILE.read_text())
        assert status["state"] == SetupState.CONNECTED
        assert status["connected_ssid"] == "HomeWifi"

    def test_tick_never_raises_on_nmcli_failure(self, clock):
        cfg = _config()
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(1, "", "nmcli: command not found")):
            wd = NetworkWatchdog(cfg)
            wd.tick()  # must not raise


class TestReadStatus:
    def test_read_status_none_when_missing(self):
        assert network_mod.read_status() is None

    def test_read_status_none_on_corrupt_json(self):
        network_mod.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        network_mod.STATUS_FILE.write_text("{not json")
        assert network_mod.read_status() is None

    def test_read_status_roundtrip(self, clock):
        cfg = _config()
        with patch.object(network_mod, "_run_nmcli", return_value=_cp(0, "")):
            NetworkWatchdog(cfg)
        status = network_mod.read_status()
        assert status["state"] == SetupState.GRACE

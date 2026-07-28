"""WLAN-Zustandsüberwachung mit automatischem Setup-Hotspot.

Läuft als eigener, schlanker systemd-Dienst (`flugradar-network-watchdog`,
`After=network.target`, vor `flugradar-display.service`) durchgehend neben
der App. Nutzt NetworkManager (`nmcli`) statt einer eigenen
hostapd/dnsmasq-Lösung -- Raspberry Pi OS Bookworm/Trixie bringt
NetworkManager standardmäßig mit, und `nmcli device wifi hotspot` deckt
alles ab, was ein Eigenbau auch könnte.

Zwei getrennte Toleranzzeiten (Abschnitt siehe Auftrag):
- Boot-Fall: kurz nach dem Start keine Verbindung -> sofort Setup-Modus,
  AUSSER es ist überhaupt kein WLAN-Profil hinterlegt (echtes Neugerät) --
  dann wird die Grace-Zeit gar nicht erst abgewartet.
- Laufzeit-Fall: eine zuvor bestehende Verbindung bricht ab -> erst eine
  Toleranzzeit lang weiter versuchen (das übernimmt NetworkManager selbst),
  nur bei anhaltendem Ausfall in den Setup-Modus wechseln.

Der aktuelle Zustand wird in eine kleine JSON-Statusdatei geschrieben
(gleiches Prinzip wie `settings.json`/`update.log`), die sowohl die
Pygame-App (Screen-Wechsel) als auch das Web-Portal (Hotspot-Zugangsdaten
im Captive-Portal-Fallback) unabhängig voneinander lesen können, ohne dass
dieser Prozess selbst etwas von ihnen wissen muss.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import string
import subprocess
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

STATUS_FILE = Path.home() / ".local" / "share" / "flugradar" / "network_status.json"

HOTSPOT_CON_NAME = "SassoRadarSetup"
DEFAULT_INTERFACE = "wlan0"

_NMCLI_TIMEOUT_S = 30
_HOTSPOT_TIMEOUT_S = 45
_CONNECT_TIMEOUT_S = 45
_POLL_INTERVAL_S = 5


class SetupState:
    """String constants (not an Enum -- these go straight into the JSON
    status file, so plain strings avoid a serialisation round-trip)."""

    CONNECTED = "connected"
    GRACE = "grace"
    OUTAGE = "outage"
    SETUP_MODE = "setup_mode"


def _run_nmcli(args: list[str], timeout: float = _NMCLI_TIMEOUT_S) -> subprocess.CompletedProcess:
    """All nmcli calls go through here (and through `sudo -n`) -- the
    watchdog/web processes run as the regular user like every other
    flugradar service, but changing network state needs root. `-n`
    (non-interactive) fails fast with a clear stderr message instead of
    hanging if the sudoers rule (see install.sh) isn't set up."""
    cmd = ["sudo", "-n", "nmcli", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _generate_password(length: int = 10) -> str:
    """Random WPA2 password (>= 8 chars) for a hotspot the user hasn't
    pinned to a fixed value via WIFI_HOTSPOT_PASSWORD."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class WatchdogConfig:
    """Deliberately reads straight from the environment rather than going
    through AppSettings/settings.json: this runs as its own early-boot
    service, independent of the display app and the portal, and must keep
    working even if settings.json is missing or corrupt. Same priority
    idea as everywhere else in the project (env > default), just without
    the portal layer -- there's nothing to configure a hotspot's own
    credentials through before the hotspot exists."""

    def __init__(
        self,
        boot_grace_s: float = 45.0,
        outage_tolerance_s: float = 300.0,
        hotspot_ssid: str = "SassoRadar-Setup",
        hotspot_password: str = "",
        interface: str = DEFAULT_INTERFACE,
    ) -> None:
        self.boot_grace_s = boot_grace_s
        self.outage_tolerance_s = outage_tolerance_s
        self.hotspot_ssid = hotspot_ssid
        self.hotspot_password = hotspot_password or _generate_password()
        self.interface = interface

    @classmethod
    def from_env(cls) -> "WatchdogConfig":
        cfg = cls()
        if v := os.environ.get("WIFI_BOOT_GRACE_S"):
            cfg.boot_grace_s = float(v)
        if v := os.environ.get("WIFI_OUTAGE_TOLERANCE_S"):
            cfg.outage_tolerance_s = float(v)
        if v := os.environ.get("WIFI_HOTSPOT_SSID"):
            cfg.hotspot_ssid = v
        if v := os.environ.get("WIFI_HOTSPOT_PASSWORD"):
            cfg.hotspot_password = v
        if v := os.environ.get("WIFI_INTERFACE"):
            cfg.interface = v
        return cfg


# --- nmcli queries -----------------------------------------------------

def active_connection_name(interface: str = DEFAULT_INTERFACE) -> Optional[str]:
    """The NetworkManager connection profile currently active on
    `interface`, or None if disconnected. For a wifi connection created by
    `nmcli device wifi connect <ssid>`, the profile name defaults to the
    SSID itself, so this doubles as "which network are we joined to"."""
    result = _run_nmcli(["-t", "-f", "GENERAL.CONNECTION", "device", "show", interface])
    if result.returncode != 0:
        return None
    _, _, name = result.stdout.strip().partition(":")
    name = name.strip()
    return name if name and name != "--" else None


def is_client_connected(interface: str = DEFAULT_INTERFACE) -> bool:
    """True only for a real client connection -- our own hotspot profile
    reports as "connected" too (it's an active NetworkManager connection,
    just in AP mode), so it's explicitly excluded here."""
    name = active_connection_name(interface)
    return bool(name) and name != HOTSPOT_CON_NAME


def has_known_wifi_profiles() -> bool:
    """True if NetworkManager has at least one saved wifi profile besides
    our own hotspot -- distinguishes "a known network is just out of
    reach right now" (outage tolerance applies) from "nothing configured
    at all" (brand-new device, skip straight to setup mode)."""
    result = _run_nmcli(["-t", "-f", "NAME,TYPE", "connection", "show"])
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        name, _, conn_type = line.partition(":")
        if conn_type == "802-11-wireless" and name != HOTSPOT_CON_NAME:
            return True
    return False


def scan_networks(interface: str = DEFAULT_INTERFACE) -> list[dict]:
    """Visible SSIDs, strongest signal first, de-duplicated, our own
    hotspot filtered out. Used by the captive-portal page to populate the
    network picker."""
    try:
        _run_nmcli(["device", "wifi", "rescan", "ifname", interface], timeout=15)
    except subprocess.TimeoutExpired:
        pass
    result = _run_nmcli(["-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "ifname", interface])
    if result.returncode != 0:
        return []
    seen: set[str] = set()
    networks: list[dict] = []
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) < 2:
            continue
        ssid = parts[0]
        signal_raw = parts[1]
        security = ":".join(parts[2:]) if len(parts) > 2 else ""
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(signal_raw)
        except ValueError:
            signal = 0
        networks.append({
            "ssid": ssid,
            "signal": signal,
            "secured": bool(security and security != "--"),
        })
    networks.sort(key=lambda n: n["signal"], reverse=True)
    return networks


# --- nmcli actions ------------------------------------------------------

def start_hotspot(ssid: str, password: str, interface: str = DEFAULT_INTERFACE) -> bool:
    result = _run_nmcli(
        [
            "device", "wifi", "hotspot",
            "ifname", interface,
            "con-name", HOTSPOT_CON_NAME,
            "ssid", ssid,
            "password", password,
        ],
        timeout=_HOTSPOT_TIMEOUT_S,
    )
    if result.returncode != 0:
        log.error("Failed to start setup hotspot: %s", result.stderr.strip())
    return result.returncode == 0


def stop_hotspot() -> None:
    _run_nmcli(["connection", "down", HOTSPOT_CON_NAME])


def connect_to_wifi(
    ssid: str, password: str, interface: str = DEFAULT_INTERFACE,
) -> tuple[bool, str]:
    """Join `ssid` as a client. On a single-radio Pi this necessarily
    preempts our own hotspot on the same interface -- NetworkManager tears
    the AP profile down to attempt the new connection, whether or not that
    attempt then succeeds. Callers that need the hotspot to survive a
    failed attempt (the captive portal route) must call start_hotspot()
    again afterwards; this function only reports what nmcli did."""
    args = ["device", "wifi", "connect", ssid, "ifname", interface]
    if password:
        args += ["password", password]
    try:
        result = _run_nmcli(args, timeout=_CONNECT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False, "Zeitüberschreitung beim Verbindungsversuch"
    ok = result.returncode == 0
    detail = result.stdout.strip() if ok else result.stderr.strip()
    return ok, detail


# --- shared status file --------------------------------------------------

def _persist_status(state: str, config: WatchdogConfig, connected_ssid: Optional[str] = None) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "hotspot_ssid": config.hotspot_ssid,
        "hotspot_password": config.hotspot_password,
        "connected_ssid": connected_ssid,
        "updated_at": time.time(),
    }
    tmp_path = STATUS_FILE.with_suffix(STATUS_FILE.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload))
    os.replace(tmp_path, STATUS_FILE)


def read_status() -> Optional[dict]:
    """Read the shared status file. Returns None if the watchdog service
    isn't running / hasn't written anything yet -- callers must treat that
    as "no opinion", not as an implicit setup-mode signal, so a device
    without the watchdog installed never gets stuck showing the WLAN
    setup screen."""
    try:
        return json.loads(STATUS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# --- state machine --------------------------------------------------------

class NetworkWatchdog:
    """Polls nmcli periodically and drives the setup-hotspot lifecycle.
    One `tick()` call advances the state machine by at most one
    transition; `run_forever()` is the systemd entry point."""

    def __init__(self, config: Optional[WatchdogConfig] = None) -> None:
        self.config = config or WatchdogConfig.from_env()
        self._state = SetupState.GRACE
        self._boot_time = time.monotonic()
        self._outage_since: Optional[float] = None
        self._write_status(SetupState.GRACE)

    def _write_status(self, state: str, connected_ssid: Optional[str] = None) -> None:
        self._state = state
        _persist_status(state, self.config, connected_ssid)

    def tick(self) -> None:
        connected = is_client_connected(self.config.interface)

        if self._state == SetupState.SETUP_MODE:
            if connected:
                self._exit_setup_mode()
            return

        if connected:
            if self._state != SetupState.CONNECTED:
                self._write_status(
                    SetupState.CONNECTED, active_connection_name(self.config.interface),
                )
            self._outage_since = None
            return

        # not connected right now
        if self._state == SetupState.CONNECTED:
            self._state = SetupState.OUTAGE
            self._outage_since = time.monotonic()
            self._write_status(SetupState.OUTAGE)
            return

        if self._state == SetupState.OUTAGE:
            assert self._outage_since is not None
            if time.monotonic() - self._outage_since >= self.config.outage_tolerance_s:
                self._enter_setup_mode()
            return

        if self._state == SetupState.GRACE:
            if not has_known_wifi_profiles():
                # brand-new device -- nothing saved to wait for
                self._enter_setup_mode()
                return
            if time.monotonic() - self._boot_time >= self.config.boot_grace_s:
                self._enter_setup_mode()
            return

    def _enter_setup_mode(self) -> None:
        log.info("No WLAN connection -- opening setup hotspot %r", self.config.hotspot_ssid)
        start_hotspot(self.config.hotspot_ssid, self.config.hotspot_password, self.config.interface)
        self._write_status(SetupState.SETUP_MODE)

    def _exit_setup_mode(self) -> None:
        log.info("WLAN configured via setup hotspot, connection restored")
        self._outage_since = None
        self._write_status(
            SetupState.CONNECTED, active_connection_name(self.config.interface),
        )

    def run_forever(self) -> None:
        while True:
            try:
                self.tick()
            except Exception:
                log.exception("Watchdog tick failed, retrying next cycle")
            time.sleep(_POLL_INTERVAL_S)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    NetworkWatchdog().run_forever()


if __name__ == "__main__":
    main()

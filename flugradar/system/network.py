"""WLAN-Zustandsüberwachung + Scan/Verbindungsaufbau über NetworkManager.

Läuft als eigener, schlanker systemd-Dienst (`flugradar-network-watchdog`,
`After=network.target`, vor `flugradar-display.service`) durchgehend neben
der App. Nutzt NetworkManager (`nmcli`) statt einer eigenen
hostapd/dnsmasq-Lösung -- Raspberry Pi OS Bookworm/Trixie bringt
NetworkManager standardmäßig mit.

**Kein Hotspot mehr** (Abweichung vom ursprünglichen QR-Code-/Hotspot-
Ansatz): die WLAN-Einrichtung läuft komplett am Gerät selbst über einen
eigenen Bildschirm (flugradar/display/screens/wifi.py) mit Netzwerkliste
und Bildschirmtastatur. Der Pi verbindet sich direkt mit dem Zielnetz
(`nmcli device wifi connect`), ohne den Umweg über einen eigenen Access
Point.

Zwei getrennte Toleranzzeiten für die automatische Erkennung:
- Boot-Fall: kurz nach dem Start keine Verbindung -> der WLAN-Screen
  erscheint sofort, AUSSER es ist überhaupt kein WLAN-Profil hinterlegt
  (echtes Neugerät) -- dann wird die Grace-Zeit gar nicht erst abgewartet.
- Laufzeit-Fall: eine zuvor bestehende Verbindung bricht ab -> erst eine
  Toleranzzeit lang weiter versuchen (das übernimmt NetworkManager selbst),
  nur bei anhaltendem Ausfall den WLAN-Screen automatisch zeigen.

Der aktuelle Zustand wird in eine kleine JSON-Statusdatei geschrieben
(gleiches Prinzip wie `settings.json`/`update.log`), die die Pygame-App
pollt, um bei einer automatischen Erkennung (Boot/Ausfall -- ein separater
Prozess) den Bildschirm zu wechseln. Der manuelle Weg übers Gerätemenü
braucht diesen Umweg nicht: er läuft im selben Prozess wie die App und
wechselt den Screen direkt.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

STATUS_FILE = Path.home() / ".local" / "share" / "flugradar" / "network_status.json"

DEFAULT_INTERFACE = "wlan0"

_NMCLI_TIMEOUT_S = 30
_SCAN_TIMEOUT_S = 15
_CONNECT_TIMEOUT_S = 45
_POLL_INTERVAL_S = 5


class SetupState:
    """String constants (not an Enum -- these go straight into the JSON
    status file, so plain strings avoid a serialisation round-trip)."""

    CONNECTED = "connected"
    GRACE = "grace"
    OUTAGE = "outage"
    NEEDS_WIFI = "needs_wifi"


def _run_nmcli(args: list[str], timeout: float = _NMCLI_TIMEOUT_S) -> subprocess.CompletedProcess:
    """All nmcli calls go through here (and through `sudo -n`) -- the
    watchdog/display processes run as the regular user like every other
    flugradar service, but changing network state needs root. `-n`
    (non-interactive) fails fast with a clear stderr message instead of
    hanging if the sudoers rule (see install.sh) isn't set up."""
    cmd = ["sudo", "-n", "nmcli", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class WatchdogConfig:
    """Reads straight from the environment rather than through AppSettings/
    settings.json: the watchdog is its own early-boot service, independent
    of the display app and the portal, and must keep working even if
    settings.json is missing or corrupt."""

    def __init__(
        self,
        boot_grace_s: float = 45.0,
        outage_tolerance_s: float = 300.0,
        interface: str = DEFAULT_INTERFACE,
    ) -> None:
        self.boot_grace_s = boot_grace_s
        self.outage_tolerance_s = outage_tolerance_s
        self.interface = interface

    @classmethod
    def from_env(cls) -> "WatchdogConfig":
        cfg = cls()
        if v := os.environ.get("WIFI_BOOT_GRACE_S"):
            cfg.boot_grace_s = float(v)
        if v := os.environ.get("WIFI_OUTAGE_TOLERANCE_S"):
            cfg.outage_tolerance_s = float(v)
        if v := os.environ.get("WIFI_INTERFACE"):
            cfg.interface = v
        return cfg


@dataclass
class NetworkInfo:
    ssid: str
    signal: int  # 0-100
    secured: bool
    is_current: bool = False


@dataclass
class ConnectResult:
    ok: bool
    # "wrong_password" | "out_of_range" | "timeout" | "unknown" | None (ok)
    error: Optional[str] = None
    message: str = ""


_ERROR_MESSAGES = {
    "wrong_password": "Falsches Passwort",
    "out_of_range": "Netzwerk außer Reichweite",
    "timeout": "Zeitüberschreitung beim Verbindungsversuch",
    "unknown": "Verbindung fehlgeschlagen",
}


def _classify_connect_error(stderr: str) -> str:
    """Best-effort classification from nmcli's stderr text -- nmcli itself
    doesn't expose a structured error code for "wrong password" vs. "out
    of range" vs. a generic activation failure, so this pattern-matches
    the wording NetworkManager is known to use for each case."""
    lower = stderr.lower()
    if "no network with ssid" in lower or "network is unreachable" in lower:
        return "out_of_range"
    if "secrets were required" in lower or "802.1x" in lower:
        return "wrong_password"
    if "timeout" in lower or "timed out" in lower:
        return "timeout"
    return "unknown"


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
    return bool(active_connection_name(interface))


def has_known_wifi_profiles() -> bool:
    """True if NetworkManager has at least one saved wifi profile --
    distinguishes "a known network is just out of reach right now"
    (outage tolerance applies) from "nothing configured at all" (brand-new
    device, skip straight to the WLAN screen)."""
    result = _run_nmcli(["-t", "-f", "NAME,TYPE", "connection", "show"])
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        _name, _, conn_type = line.partition(":")
        if conn_type == "802-11-wireless":
            return True
    return False


def scan_networks(interface: str = DEFAULT_INTERFACE) -> list[NetworkInfo]:
    """Visible SSIDs, strongest signal first, de-duplicated (multiple APs
    for the same SSID collapse to the strongest one seen). Blocking --
    callers on the display side run this in a background thread."""
    try:
        _run_nmcli(["device", "wifi", "rescan", "ifname", interface], timeout=_SCAN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        pass
    result = _run_nmcli(["-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "ifname", interface])
    if result.returncode != 0:
        return []
    current = active_connection_name(interface)
    best: dict[str, NetworkInfo] = {}
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) < 2:
            continue
        ssid = parts[0]
        signal_raw = parts[1]
        security = ":".join(parts[2:]) if len(parts) > 2 else ""
        if not ssid:
            continue
        try:
            signal = int(signal_raw)
        except ValueError:
            signal = 0
        existing = best.get(ssid)
        if existing is not None and existing.signal >= signal:
            continue
        best[ssid] = NetworkInfo(
            ssid=ssid,
            signal=signal,
            secured=bool(security and security != "--"),
            is_current=(ssid == current),
        )
    networks = list(best.values())
    networks.sort(key=lambda n: n.signal, reverse=True)
    return networks


def connect(ssid: str, password: Optional[str], interface: str = DEFAULT_INTERFACE) -> ConnectResult:
    """Join `ssid` as a client, blocking until nmcli reports success/
    failure. Callers on the display side run this in a background thread
    so the UI (and the sweep animation elsewhere in the app) doesn't
    freeze for the several seconds a real association/DHCP handshake
    takes."""
    args = ["device", "wifi", "connect", ssid, "ifname", interface]
    if password:
        args += ["password", password]
    try:
        result = _run_nmcli(args, timeout=_CONNECT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return ConnectResult(False, "timeout", _ERROR_MESSAGES["timeout"])
    if result.returncode == 0:
        return ConnectResult(True)
    error = _classify_connect_error(result.stderr)
    return ConnectResult(False, error, _ERROR_MESSAGES[error])


# --- shared status file --------------------------------------------------

def _persist_status(state: str, connected_ssid: Optional[str] = None) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "connected_ssid": connected_ssid,
        "updated_at": time.time(),
    }
    tmp_path = STATUS_FILE.with_suffix(STATUS_FILE.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload))
    os.replace(tmp_path, STATUS_FILE)


def read_status() -> Optional[dict]:
    """Read the shared status file. Returns None if the watchdog service
    isn't running / hasn't written anything yet -- callers must treat that
    as "no opinion", not as an implicit needs-wifi signal, so a device
    without the watchdog installed never gets stuck on the WLAN screen."""
    try:
        return json.loads(STATUS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# --- state machine --------------------------------------------------------

class NetworkWatchdog:
    """Polls nmcli periodically and tracks whether the device needs the
    WLAN screen. One `tick()` call advances the state machine by at most
    one transition; `run_forever()` is the systemd entry point."""

    def __init__(self, config: Optional[WatchdogConfig] = None) -> None:
        self.config = config or WatchdogConfig.from_env()
        self._state = SetupState.GRACE
        self._boot_time = time.monotonic()
        self._outage_since: Optional[float] = None
        self._write_status(SetupState.GRACE)

    def _write_status(self, state: str, connected_ssid: Optional[str] = None) -> None:
        self._state = state
        _persist_status(state, connected_ssid)

    def tick(self) -> None:
        connected = is_client_connected(self.config.interface)

        if self._state == SetupState.NEEDS_WIFI:
            if connected:
                self._wifi_configured()
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
                self._needs_wifi()
            return

        if self._state == SetupState.GRACE:
            if not has_known_wifi_profiles():
                # brand-new device -- nothing saved to wait for
                self._needs_wifi()
                return
            if time.monotonic() - self._boot_time >= self.config.boot_grace_s:
                self._needs_wifi()
            return

    def _needs_wifi(self) -> None:
        log.info("No WLAN connection -- WLAN screen needed")
        self._write_status(SetupState.NEEDS_WIFI)

    def _wifi_configured(self) -> None:
        log.info("WLAN connection restored")
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

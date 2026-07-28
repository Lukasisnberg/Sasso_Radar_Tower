"""Self-update: pull the latest code from GitHub and apply it in place.

Triggered from the on-device System menu or the web portal (both call
`trigger_update_async()`, mirroring how `system_action()` already handles
reboot/shutdown fire-and-forget). Runs as a detached background process
because the update's own final step reboots the very device that
requested it -- waiting around for that synchronously isn't possible.

Deliberately more cautious than a bare `git pull && restart`: the device
this runs on is meant to sit unattended (e.g. a living-room clock) with
no keyboard or screen to fix a broken update from. Before touching any
running service, it checks the working tree is clean, verifies the new
code at least imports, and installs dependencies -- rolling back to the
previous commit and leaving the running app untouched if anything fails,
rather than risking a bricked device.

A successful update ends in a full reboot rather than just restarting
flugradar-web/flugradar-display: some changes (boot config overlays,
apt packages pulled in by a re-run of install.sh, kernel/driver state)
only take effect after a real reboot, and a service-only restart left
those silently un-applied until someone rebooted by hand.
"""

from __future__ import annotations

import datetime
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from flugradar.system.actions import system_action

log = logging.getLogger(__name__)

REPO_DIR = Path(__file__).resolve().parents[2]
LOG_FILE = Path.home() / ".local" / "share" / "flugradar" / "update.log"

_GIT_TIMEOUT_S = 120
_PIP_TIMEOUT_S = 600
_IMPORT_TIMEOUT_S = 30


@dataclass
class UpdateResult:
    ok: bool
    message: str


def _run(cmd: list[str], timeout: float = _GIT_TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=REPO_DIR, capture_output=True, text=True, timeout=timeout,
    )


def _rollback(sha: str) -> None:
    _run(["git", "reset", "--hard", sha])


def apply_update() -> UpdateResult:
    """Does the actual work; safe to call synchronously (e.g. from a test
    or from within the already-detached background process)."""
    try:
        fetch = _run(["git", "fetch", "origin", "main"])
    except (subprocess.TimeoutExpired, OSError) as exc:
        return UpdateResult(False, f"Abruf fehlgeschlagen: {exc}")
    if fetch.returncode != 0:
        return UpdateResult(False, f"Abruf fehlgeschlagen: {fetch.stderr.strip()}")

    status = _run(["git", "status", "--porcelain"])
    if status.stdout.strip():
        return UpdateResult(False, "lokale Änderungen im Installationsverzeichnis vorhanden, Überschreiben verweigert")

    previous_sha = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    target_sha = _run(["git", "rev-parse", "origin/main"]).stdout.strip()
    if not previous_sha or not target_sha:
        return UpdateResult(False, "aktueller/entfernter Commit konnte nicht ermittelt werden")
    if previous_sha == target_sha:
        return UpdateResult(True, "bereits aktuell")

    reset = _run(["git", "reset", "--hard", "origin/main"])
    if reset.returncode != 0:
        return UpdateResult(False, f"Checkout von {target_sha[:8]} fehlgeschlagen: {reset.stderr.strip()}")

    try:
        pip = _run(
            [sys.executable, "-m", "pip", "install", "-e", f"{REPO_DIR}[display,web]"],
            timeout=_PIP_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        _rollback(previous_sha)
        return UpdateResult(False, f"Zeitüberschreitung bei der Abhängigkeitsinstallation, zurückgesetzt auf {previous_sha[:8]}")
    if pip.returncode != 0:
        _rollback(previous_sha)
        return UpdateResult(
            False, f"Abhängigkeitsinstallation fehlgeschlagen, zurückgesetzt auf {previous_sha[:8]}: {pip.stderr.strip()[-500:]}",
        )

    sanity = _run(
        [sys.executable, "-c", "import flugradar.display.app; import flugradar.web.app"],
        timeout=_IMPORT_TIMEOUT_S,
    )
    if sanity.returncode != 0:
        _rollback(previous_sha)
        return UpdateResult(
            False, f"Neuer Code bei {target_sha[:8]} ließ sich nicht importieren, zurückgesetzt auf {previous_sha[:8]}: "
            f"{sanity.stderr.strip()[-500:]}",
        )

    # A full reboot (not just restarting the two services) so that
    # anything beyond plain Python code -- boot config, apt packages, a
    # re-run of install.sh -- is guaranteed to be picked up too. Fire-and-
    # forget, same as system_action("reboot") from the menu/portal: this
    # process (possibly running inside flugradar-display.service, the very
    # thing about to go down) never sees the reboot actually happen, but by
    # the time we return, the request has already been dispatched to
    # systemd/PID 1, so it completes regardless.
    system_action("reboot")

    return UpdateResult(True, f"aktualisiert {previous_sha[:8]} -> {target_sha[:8]}, Neustart eingeleitet")


def run_and_log() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = apply_update()
    except Exception as exc:  # noqa: BLE001 -- this is the top of a detached process, must not crash silently
        result = UpdateResult(False, f"unerwarteter Fehler: {exc!r}")
        log.exception("Update crashed")
    with open(LOG_FILE, "a") as f:
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        f.write(f"{stamp} {'OK' if result.ok else 'FAILED'}: {result.message}\n")


def trigger_update_async() -> None:
    """Fire-and-forget: hand off to a detached process and return
    immediately so the caller (pygame event loop / Flask request) never
    blocks on network/pip/restart."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(LOG_FILE, "a")
        subprocess.Popen(
            [sys.executable, "-m", "flugradar.system.update"],
            cwd=str(REPO_DIR),
            stdout=log_fh, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception:
        log.exception("Failed to launch update process")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_and_log()

"""Self-update: pull the latest code from GitHub and apply it in place.

Triggered from the on-device System menu or the web portal (both call
`trigger_update_async()`, mirroring how `system_action()` already handles
reboot/shutdown fire-and-forget). Runs as a detached background process
because the update's own final step restarts the very service that
requested it -- waiting around for that synchronously isn't possible.

Deliberately more cautious than a bare `git pull && restart`: the device
this runs on is meant to sit unattended (e.g. a living-room clock) with
no keyboard or screen to fix a broken update from. Before touching any
running service, it checks the working tree is clean, verifies the new
code at least imports, and installs dependencies -- rolling back to the
previous commit and leaving the running app untouched if anything fails,
rather than risking a bricked device.
"""

from __future__ import annotations

import datetime
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

REPO_DIR = Path(__file__).resolve().parents[2]
LOG_FILE = Path.home() / ".local" / "share" / "flugradar" / "update.log"

_GIT_TIMEOUT_S = 120
_PIP_TIMEOUT_S = 600
_IMPORT_TIMEOUT_S = 30
_RESTART_TIMEOUT_S = 60


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
        return UpdateResult(False, f"fetch failed: {exc}")
    if fetch.returncode != 0:
        return UpdateResult(False, f"fetch failed: {fetch.stderr.strip()}")

    status = _run(["git", "status", "--porcelain"])
    if status.stdout.strip():
        return UpdateResult(False, "local changes present in the install dir, refusing to overwrite")

    previous_sha = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    target_sha = _run(["git", "rev-parse", "origin/main"]).stdout.strip()
    if not previous_sha or not target_sha:
        return UpdateResult(False, "could not resolve current/remote commit")
    if previous_sha == target_sha:
        return UpdateResult(True, "already up to date")

    reset = _run(["git", "reset", "--hard", "origin/main"])
    if reset.returncode != 0:
        return UpdateResult(False, f"checkout of {target_sha[:8]} failed: {reset.stderr.strip()}")

    try:
        pip = _run(
            [sys.executable, "-m", "pip", "install", "-e", f"{REPO_DIR}[display,web]"],
            timeout=_PIP_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        _rollback(previous_sha)
        return UpdateResult(False, f"dependency install timed out, rolled back to {previous_sha[:8]}")
    if pip.returncode != 0:
        _rollback(previous_sha)
        return UpdateResult(
            False, f"dependency install failed, rolled back to {previous_sha[:8]}: {pip.stderr.strip()[-500:]}",
        )

    sanity = _run(
        [sys.executable, "-c", "import flugradar.display.app; import flugradar.web.app"],
        timeout=_IMPORT_TIMEOUT_S,
    )
    if sanity.returncode != 0:
        _rollback(previous_sha)
        return UpdateResult(
            False, f"new code at {target_sha[:8]} failed to import, rolled back to {previous_sha[:8]}: "
            f"{sanity.stderr.strip()[-500:]}",
        )

    # The web service's cgroup is unrelated to whoever's making this
    # request, so it always restarts cleanly. flugradar-display.service is
    # restarted last since if *this* process happens to be running inside
    # it, systemd may tear down this very call mid-flight -- by then the
    # restart request has already been dispatched to systemd (PID 1, not
    # us), so the restart itself still completes even if we don't get to
    # see the exit code.
    _run(["sudo", "systemctl", "restart", "flugradar-web.service"], timeout=_RESTART_TIMEOUT_S)
    _run(["sudo", "systemctl", "restart", "flugradar-display.service"], timeout=_RESTART_TIMEOUT_S)

    return UpdateResult(True, f"updated {previous_sha[:8]} -> {target_sha[:8]}")


def run_and_log() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = apply_update()
    except Exception as exc:  # noqa: BLE001 -- this is the top of a detached process, must not crash silently
        result = UpdateResult(False, f"unexpected error: {exc!r}")
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

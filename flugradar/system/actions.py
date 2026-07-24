"""System-level actions (reboot/shutdown), shared by the web portal and the
on-device settings menu so neither has to shell out on its own."""

import logging
import subprocess

log = logging.getLogger(__name__)


def system_action(action: str) -> None:
    try:
        if action == "reboot":
            subprocess.Popen(["sudo", "reboot"])
        elif action == "shutdown":
            subprocess.Popen(["sudo", "shutdown", "-h", "now"])
    except Exception:
        log.exception("System action '%s' failed", action)

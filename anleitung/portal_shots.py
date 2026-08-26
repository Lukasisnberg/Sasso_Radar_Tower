"""Screenshots des Web-Portals für die Buch-Seiten 24-26.

Startet `create_app()` (`flugradar/web/app.py`) gegen ein leeres,
temporäres Datenverzeichnis auf einem freien lokalen Port, fotografiert
ausgewählte Seiten mit dem im System vorhandenen headless Chromium im
Telefonformat und beendet den Server wieder.

Leeres Datenverzeichnis + keine gesetzten API-Schlüssel ist Absicht: die
Schlüsselfelder zeigen im Screenshot „Nicht gesetzt" statt echter Werte --
es kann so nichts Persönliches ins gedruckte Buch geraten.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

_DATA_DIR = Path(tempfile.mkdtemp(prefix="srt-anleitung-portal-"))
os.environ["FLUGRADAR_DATA_DIR"] = str(_DATA_DIR)

from flugradar.config.settings import AppSettings  # noqa: E402
from flugradar.web.app import create_app  # noqa: E402

from anleitung import szene  # noqa: E402

CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
WINDOW = "480,1000"  # schmales Telefonformat -- das Portal ist responsiv
PAGES = ("", "radar", "display", "api-keys")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise TimeoutError(f"Portal auf Port {port} startete nicht rechtzeitig")


def render_all(out_dir: Path) -> list[Path]:
    if not Path(CHROMIUM).exists():
        raise SystemExit(f"Chromium fehlt unter {CHROMIUM}")

    out_dir.mkdir(parents=True, exist_ok=True)

    settings = AppSettings()
    settings.home.lat = szene.HOME_LAT
    settings.home.lon = szene.HOME_LON
    settings.home.radius_km = 100.0
    app = create_app(settings=settings)

    from werkzeug.serving import make_server

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _wait_for_port(port)
        paths = []
        for page in PAGES:
            name = f"portal-{page or 'start'}"
            out_path = out_dir / f"{name}.png"
            url = f"http://127.0.0.1:{port}/{page}"
            result = subprocess.run(
                [
                    CHROMIUM, "--headless", "--disable-gpu", "--no-sandbox",
                    "--hide-scrollbars", f"--window-size={WINDOW}",
                    f"--screenshot={out_path}", url,
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0 or not out_path.exists():
                raise RuntimeError(
                    f"Chromium-Screenshot für {url} fehlgeschlagen:\n{result.stderr}"
                )
            paths.append(out_path)
        return paths
    finally:
        server.shutdown()
        thread.join(timeout=5)
        shutil.rmtree(_DATA_DIR, ignore_errors=True)


if __name__ == "__main__":
    default_out = Path(__file__).parent / "bilder"
    paths = render_all(default_out)
    print(f"{len(paths)} Portal-Bilder geschrieben nach {default_out}", file=sys.stderr)

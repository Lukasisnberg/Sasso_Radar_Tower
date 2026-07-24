"""RainViewer weather-maps API client — latest radar frame lookup.

Free, no API key required. Attribution requirement (verbatim from
https://www.rainviewer.com/api.html): "We kindly ask you to mention the
RainViewer API as a source of the data on your website with a link:
https://www.rainviewer.com/". Per the same page: "The API is free for
personal or educational use only" — consistent with this project.

Verified live against https://api.rainviewer.com/public/weather-maps.json
on 2026-07-24: response has "host" (tile cache base URL) and
"radar": {"past": [...], "nowcast": [...]}, each frame a
{"time": unix_ts, "path": "/v2/radar/<id>"}. Tile URL template:
{host}{path}/{size}/{z}/{x}/{y}/{color}/{smooth}_{snow}.png — confirmed
working live with size=256, color=2, smooth=1, snow=1. Max zoom is 7
(coarse radar resolution, not meant for close-in tiles). Radar data
refreshes roughly every 5 minutes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

_INDEX_URL = "https://api.rainviewer.com/public/weather-maps.json"
_REFRESH_TTL_S = 5 * 60.0
_UA = "SassoRadarTower/1.0 (+https://github.com/Lukasisnberg/Sasso_Radar_Tower)"


class RainViewerClient:
    """Looks up the latest available radar frame's tile path.

    Fetches the small frame-index JSON on a short TTL. Network failures
    never raise -- callers get back the last-known-good frame path (or
    "" if nothing has ever succeeded), so a RainViewer outage can't crash
    or stall the map. Callers are expected to invoke latest_frame_path()
    off the main thread (it can block on the TTL-expiry fetch).
    """

    def __init__(self, ttl_s: float = _REFRESH_TTL_S) -> None:
        self._ttl_s = ttl_s
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _UA
        self._host = ""
        self._path = ""
        # None (not 0.0) means "never fetched" -- time.monotonic()'s epoch
        # is unspecified and can itself be a small number, so a 0.0
        # sentinel can wrongly look "fresh" on the very first call.
        self._fetched_at: Optional[float] = None

    def latest_frame_path(self) -> str:
        """Returns "{host}{path}" of the latest past radar frame, or ""
        if no frame has ever been resolved successfully."""
        now = time.monotonic()
        with self._lock:
            stale = self._fetched_at is None or (now - self._fetched_at) >= self._ttl_s
            current = f"{self._host}{self._path}" if self._host else ""
        if not stale:
            return current
        self._refresh()
        with self._lock:
            return f"{self._host}{self._path}" if self._host else ""

    def frame_changed_since(self, previous_path: str) -> bool:
        return self.latest_frame_path() != previous_path

    def _refresh(self) -> None:
        try:
            resp = self._session.get(_INDEX_URL, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            host = data.get("host") or ""
            past = (data.get("radar") or {}).get("past") or []
            path = past[-1].get("path") if past else ""
            if not host or not path:
                return
        except (requests.RequestException, ValueError) as exc:
            log.debug("RainViewer frame index fetch failed: %s", exc)
            with self._lock:
                self._fetched_at = time.monotonic()  # don't hammer on repeated failure
            return

        with self._lock:
            self._host = host
            self._path = path
            self._fetched_at = time.monotonic()

    def close(self) -> None:
        self._session.close()

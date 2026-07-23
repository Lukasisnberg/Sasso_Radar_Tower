"""Aircraft photo lookup via planespotters.net with disk cache.

Planespotters (free, non-commercial, attribution required):
  GET https://api.planespotters.net/pub/photos/hex/{icao}
  GET https://api.planespotters.net/pub/photos/reg/{registration}

Photos are cached on disk with a 2-week TTL. Lookups run in a background
thread so the display loop never blocks on network I/O.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Optional

import requests

log = logging.getLogger(__name__)

_UA = "SassoRadarTower/1.0 (+https://github.com/Lukasisnberg/Sasso_Radar_Tower)"
_API_HEX = "https://api.planespotters.net/pub/photos/hex"
_API_REG = "https://api.planespotters.net/pub/photos/reg"
_SEARCH_TIMEOUT = 8
_DOWNLOAD_TIMEOUT = 12
_META_TTL_S = 14 * 24 * 3600
_THUMB_WIDTH = 480

_DATA_DIR = Path(os.environ.get(
    "FLUGRADAR_DATA_DIR",
    Path.home() / ".local" / "share" / "flugradar",
))
_CACHE_DIR = _DATA_DIR / "aircraft_photos"
_META_PATH = _CACHE_DIR / "index.json"

_lock = threading.RLock()
_meta: Optional[dict[str, Any]] = None
_pending: set[str] = set()


def _ensure_cache_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_meta() -> dict[str, Any]:
    global _meta
    with _lock:
        if _meta is not None:
            return _meta
        _ensure_cache_dir()
        try:
            _meta = json.loads(_META_PATH.read_text())
            if not isinstance(_meta, dict):
                _meta = {}
        except (OSError, json.JSONDecodeError, TypeError):
            _meta = {}
        return _meta


def _save_meta() -> None:
    with _lock:
        _ensure_cache_dir()
        tmp = str(_META_PATH) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_meta or {}, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, str(_META_PATH))


def normalize_hex(value: str) -> str:
    hex_id = re.sub(r"[^0-9a-fA-F]", "", str(value or "").strip())
    if len(hex_id) < 6:
        return ""
    return hex_id[-6:].lower()


def normalize_reg(value: str) -> str:
    reg = re.sub(r"\s+", "", str(value or "").strip().upper())
    reg = re.sub(r"[^A-Z0-9\-]", "", reg)
    return reg if len(reg) >= 3 else ""


def _pick_image_url(photo: dict) -> str:
    for key in ("thumbnail_large", "thumbnail"):
        block = photo.get(key)
        if isinstance(block, dict):
            src = (block.get("src") or "").strip()
            if src:
                return src
        elif isinstance(block, str) and block.strip():
            return block.strip()
    link = photo.get("link")
    if isinstance(link, str) and link.startswith("http"):
        return link
    return ""


def _download_image(url: str, dest: str) -> bool:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _UA},
            timeout=_DOWNLOAD_TIMEOUT,
            stream=True,
        )
        resp.raise_for_status()
        tmp = dest + ".tmp"
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)
        os.replace(tmp, dest)
        return os.path.isfile(dest) and os.path.getsize(dest) > 100
    except (requests.RequestException, OSError) as exc:
        log.warning("[photo] download failed: %s", exc)
        return False


def _planespotters_lookup(url: str) -> Optional[dict]:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=_SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("[photo] planespotters request failed: %s", exc)
        return None
    photos = data.get("photos") if isinstance(data, dict) else None
    if not photos:
        return None
    return photos[0] if isinstance(photos[0], dict) else None


def _extract_credit(photo: dict) -> str:
    photographer = photo.get("photographer") or ""
    if isinstance(photographer, dict):
        photographer = photographer.get("name") or ""
    link = photo.get("link") or ""
    if photographer and link:
        return f"Photo: {photographer} (planespotters.net)"
    if photographer:
        return f"Photo: {photographer}"
    return "Photo: planespotters.net"


def _do_lookup(icao_hex: str, registration: str = "") -> None:
    hex_id = normalize_hex(icao_hex)
    if not hex_id:
        return

    now = time.time()
    meta = _load_meta()

    with _lock:
        entry = meta.get(hex_id)
        if entry and (now - entry.get("ts", 0)) < _META_TTL_S:
            return

    photo = None
    if hex_id:
        photo = _planespotters_lookup(f"{_API_HEX}/{hex_id}")

    reg = normalize_reg(registration)
    if not photo and reg:
        photo = _planespotters_lookup(f"{_API_REG}/{reg}")

    if not photo:
        with _lock:
            meta[hex_id] = {"miss": True, "ts": now, "hex": hex_id}
            _save_meta()
        return

    img_url = _pick_image_url(photo)
    if not img_url:
        with _lock:
            meta[hex_id] = {"miss": True, "ts": now, "hex": hex_id}
            _save_meta()
        return

    _ensure_cache_dir()
    dest = str(_CACHE_DIR / f"{hex_id}.jpg")
    ok = _download_image(img_url, dest)

    if not ok:
        with _lock:
            meta[hex_id] = {"miss": True, "ts": now, "hex": hex_id}
            _save_meta()
        return

    credit = _extract_credit(photo)
    with _lock:
        meta[hex_id] = {
            "miss": False,
            "ts": now,
            "hex": hex_id,
            "path": dest,
            "credit": credit,
            "source": "planespotters",
        }
        _save_meta()
    log.info("[photo] cached %s → %s", hex_id, dest)


def request_photo(icao_hex: str, registration: str = "") -> None:
    hex_id = normalize_hex(icao_hex)
    if not hex_id:
        return
    with _lock:
        if hex_id in _pending:
            return
        meta = _load_meta()
        entry = meta.get(hex_id)
        if entry and (time.time() - entry.get("ts", 0)) < _META_TTL_S:
            return
        _pending.add(hex_id)

    def _worker():
        try:
            _do_lookup(hex_id, registration)
        finally:
            with _lock:
                _pending.discard(hex_id)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def get_photo_info(icao_hex: str) -> Optional[dict[str, str]]:
    hex_id = normalize_hex(icao_hex)
    if not hex_id:
        return None
    meta = _load_meta()
    with _lock:
        entry = meta.get(hex_id)
    if not entry or entry.get("miss"):
        return None
    path = entry.get("path", "")
    if not path or not os.path.isfile(path):
        return None
    return {"path": path, "credit": entry.get("credit", "")}


def load_photo_surface(
    path: str,
    max_h: int,
    max_w: int = 0,
    radius: int = 0,
) -> Optional["pygame.Surface"]:
    import pygame

    try:
        image = pygame.image.load(path).convert_alpha()
    except (pygame.error, FileNotFoundError):
        return None

    w, h = image.get_size()
    if w <= 0 or h <= 0:
        return None

    scale = min(max_h / h, (max_w / w) if max_w > 0 else 1.0)
    if scale < 1.0:
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        image = pygame.transform.smoothscale(image, (new_w, new_h))

    if radius > 0:
        w, h = image.get_size()
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=radius)
        image.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

    return image

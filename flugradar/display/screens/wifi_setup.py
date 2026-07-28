"""WLAN-Einrichtungs-Screen -- gezeigt, wenn kein bekanntes Netzwerk erreichbar ist.

Wird von RadarApp erzwungen angezeigt (nicht Teil der normalen
Swipe-Reihenfolge), sobald `flugradar-network-watchdog`
(flugradar/system/network_watchdog.py) seinen Setup-Hotspot öffnet, und
zeigt Standard-WIFI-QR-Code, SSID/Passwort im Klartext als Fallback,
Anleitung und Live-Status.
"""

from __future__ import annotations

from typing import Optional

import pygame

from flugradar.display import scaling
from flugradar.display.draw_helpers import draw_center_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme

try:
    import qrcode
except ImportError:  # pragma: no cover -- optional dependency, see pyproject.toml [display]
    qrcode = None


def _render_qr(payload: str, target_size: int, colour: tuple[int, int, int]) -> Optional[pygame.Surface]:
    """Renders a QR code straight into a pygame Surface -- no file/image
    round-trip needed since `qrcode`'s matrix is just a 2D grid of booleans."""
    if qrcode is None:
        return None
    qr = qrcode.QRCode(border=1)
    qr.add_data(payload)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    modules = len(matrix)
    if modules == 0:
        return None
    module_px = max(1, target_size // modules)
    pixels = module_px * modules
    surf = pygame.Surface((pixels, pixels))
    surf.fill((255, 255, 255))
    for row_idx, row in enumerate(matrix):
        for col_idx, dark in enumerate(row):
            if dark:
                pygame.draw.rect(
                    surf, colour,
                    (col_idx * module_px, row_idx * module_px, module_px, module_px),
                )
    return surf


class WifiSetupScreen:
    """Full-screen QR code + credentials fallback + live status."""

    # brief confirmation window: keep showing "Verbunden mit X" for a
    # moment before RadarApp switches back to the radar screen, instead of
    # jumping away the instant the state flips.
    SUCCESS_DISPLAY_S = 4.0

    def __init__(self, screen_size: int, theme: Theme) -> None:
        self.size = screen_size
        self.theme = theme
        self._fonts_ready = False
        self._font_title: Optional[pygame.font.Font] = None
        self._font_value: Optional[pygame.font.Font] = None
        self._font_small: Optional[pygame.font.Font] = None
        self._ssid = ""
        self._password = ""
        self._connected_ssid = ""
        self._state = "setup_mode"
        self._qr_surface: Optional[pygame.Surface] = None
        self._qr_cache_key: Optional[tuple] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._font_title = get_font(scaling.s(TOKENS.font_title), bold=True)
            self._font_value = get_font(scaling.s(TOKENS.font_value), mono=True)
            self._font_small = get_font(scaling.s(TOKENS.font_small))
            self._fonts_ready = True

    def set_status(self, status: dict) -> None:
        self._ssid = status.get("hotspot_ssid", "") or ""
        self._password = status.get("hotspot_password", "") or ""
        self._connected_ssid = status.get("connected_ssid", "") or ""
        self._state = status.get("state", "setup_mode")

    def _ensure_qr(self) -> None:
        key = (self._ssid, self._password)
        if self._qr_cache_key == key:
            return
        target_size = int(scaling.visible_radius() * 0.85)
        payload = f"WIFI:T:WPA;S:{self._ssid};P:{self._password};;"
        self._qr_surface = _render_qr(payload, target_size, self.theme.background)
        self._qr_cache_key = key

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        self._ensure_qr()
        surface.fill(self.theme.background)

        cx = scaling.center_x()
        y = int(scaling.visible_radius() * 0.10)

        y = draw_center_text(surface, "WLAN-Einrichtung", y, self._font_title, self.theme.label)
        y += scaling.s(8)

        if self._qr_surface is not None:
            qr_x = cx - self._qr_surface.get_width() // 2
            # white quiet-zone card behind the QR code -- module colour is
            # the theme background, so it needs contrast against itself
            pad = scaling.s(6)
            card = pygame.Rect(
                qr_x - pad, y - pad,
                self._qr_surface.get_width() + pad * 2,
                self._qr_surface.get_height() + pad * 2,
            )
            pygame.draw.rect(surface, (255, 255, 255), card)
            surface.blit(self._qr_surface, (qr_x, y))
            y += self._qr_surface.get_height() + pad * 2 + scaling.s(10)
        else:
            y = draw_center_text(
                surface, "QR-Code nicht verfügbar", y, self._font_small, self.theme.hint,
            )
            y += scaling.s(6)

        y = draw_center_text(surface, f"SSID: {self._ssid}", y, self._font_value, self.theme.label)
        y = draw_center_text(surface, f"Passwort: {self._password}", y, self._font_value, self.theme.label)
        y += scaling.s(8)

        y = draw_center_text(
            surface, "1. QR-Code scannen  2. Im geöffneten Portal neues WLAN auswählen",
            y, self._font_small, self.theme.muted,
        )
        y += scaling.s(6)

        if self._state == "connected":
            status_text = f"Verbunden mit {self._connected_ssid}" if self._connected_ssid else "Verbunden"
        else:
            status_text = "Warte auf Konfiguration…"
        y = draw_center_text(surface, status_text, y, self._font_small, self.theme.sweep_colour)

        y += scaling.s(4)
        draw_center_text(surface, "rechts/runter wischen: abbrechen", y, self._font_small, self.theme.hint)

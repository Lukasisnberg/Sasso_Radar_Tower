"""WLAN-Screen -- Netzwerkliste, Passwort-Eingabe, Verbindungsstatus.

Ersetzt den früheren QR-Code-/Hotspot-Ansatz vollständig: der Pi verbindet
sich direkt mit dem Zielnetz (flugradar/system/network.py -- scan_networks()/
connect()), kein eigener Access Point mehr nötig. Wird von RadarApp
erzwungen angezeigt (nicht Teil der normalen Swipe-Reihenfolge), sobald der
Netzwerk-Watchdog eine fehlende Verbindung meldet (automatisch), oder
manuell über das Gerätemenü ("WLAN einrichten").

Scan und Verbindungsaufbau laufen blockierend in einem Hintergrund-Thread
(mehrere Sekunden für einen echten Assoziations-/DHCP-Vorgang) -- `update()`
muss jeden Frame von RadarApp aufgerufen werden, um das Ergebnis
einzusammeln, damit die Sweep-Animation anderswo in der App währenddessen
nicht einfriert.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Optional

import pygame

from flugradar.display import nav, scaling, ui_icons
from flugradar.display.draw_helpers import draw_center_text, fit_text
from flugradar.display.fonts import get_font
from flugradar.display.keyboard import OnScreenKeyboard
from flugradar.display.theme import TOKENS, Theme
from flugradar.system import network

# Confirmation window: keep showing "Verbunden mit X" for a moment before
# RadarApp switches back to the radar screen, instead of jumping away the
# instant the connection succeeds.
SUCCESS_DISPLAY_S = 3.0

# Bucketed the same way the old hand-drawn 4-bar gauge already was
# (signal < 25/50/75) -- weakest to strongest, matching Lucide's discrete
# signal-strength icon family.
_SIGNAL_ICONS = ("signal-low", "signal-medium", "signal-high", "signal")


def _draw_signal_icon(
    surface: pygame.Surface, right_x: int, cy: int, signal: int, color: tuple[int, int, int],
) -> int:
    """Bucketed signal-strength icon, right-aligned at `right_x`, vertically
    centred on `cy`. Returns the icon's width so callers can position
    something (the lock icon) to its left."""
    bucket = 0 if signal < 25 else 1 if signal < 50 else 2 if signal < 75 else 3
    size = scaling.s(TOKENS.icon_small)
    ui_icons.draw_icon(surface, _SIGNAL_ICONS[bucket], (right_x - size // 2, cy), size, color)
    return size


class WifiScreen:
    """Netzwerkliste -> Passwort-Eingabe -> Verbindungsaufbau -> Ergebnis."""

    def __init__(self, screen_size: int, theme: Theme) -> None:
        self.size = screen_size
        self.theme = theme
        self._mode = "list"  # list | password | connecting | result
        self._networks: list[network.NetworkInfo] = []
        self._scanning = False
        self._scan_lock = threading.Lock()
        self._scan_result: Optional[list[network.NetworkInfo]] = None
        self._connect_lock = threading.Lock()
        self._connect_result: Optional[network.ConnectResult] = None
        self._selected: Optional[network.NetworkInfo] = None
        self._keyboard = OnScreenKeyboard(screen_size, theme)
        self._masked = True
        self._scroll = nav.ScrollState()
        self._row_rects: list[tuple[pygame.Rect, network.NetworkInfo]] = []
        self._back_rect = pygame.Rect(0, 0, 0, 0)
        self._reload_rect = pygame.Rect(0, 0, 0, 0)
        self._eye_rect = pygame.Rect(0, 0, 0, 0)
        self._error_message: Optional[str] = None
        self._result_ok = False
        self._result_ssid = ""
        self._result_since: Optional[float] = None
        self._connect_started_at = 0.0
        self._fonts_ready = False
        self._font_title: Optional[pygame.font.Font] = None
        self._font_label: Optional[pygame.font.Font] = None
        self._font_value: Optional[pygame.font.Font] = None
        self._font_small: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._font_title = get_font(scaling.s(TOKENS.font_title), bold=True)
            self._font_label = get_font(scaling.s(TOKENS.font_standard))
            self._font_value = get_font(scaling.s(TOKENS.font_value), mono=True)
            self._font_small = get_font(scaling.s(TOKENS.font_small))
            self._fonts_ready = True

    # ---- scanning / connecting (background thread) ----------------------

    def start_scan(self) -> None:
        self._mode = "list"
        self._error_message = None
        self._scroll.reset()
        if self._scanning:
            return
        self._scanning = True
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        result = network.scan_networks()
        with self._scan_lock:
            self._scan_result = result

    def _start_connect(self, ssid: str, password: Optional[str]) -> None:
        self._mode = "connecting"
        self._connect_started_at = time.monotonic()
        threading.Thread(target=self._connect_worker, args=(ssid, password), daemon=True).start()

    def _connect_worker(self, ssid: str, password: Optional[str]) -> None:
        result = network.connect(ssid, password)
        with self._connect_lock:
            self._connect_result = result

    def update(self, now: float) -> None:
        """Call every frame while this screen is active -- drains
        background-thread results without blocking the render loop."""
        with self._scan_lock:
            if self._scan_result is not None:
                self._networks = self._scan_result
                self._scan_result = None
                self._scanning = False

        with self._connect_lock:
            result = self._connect_result
            self._connect_result = None
        if result is not None:
            if result.ok:
                self._mode = "result"
                self._result_ok = True
                self._result_ssid = self._selected.ssid if self._selected else ""
                self._result_since = now
            else:
                self._mode = "password" if (self._selected and self._selected.secured) else "list"
                self._result_ok = False
                self._error_message = result.message
                # keep whatever the user already typed -- retyping a long
                # password from scratch after a typo is exactly what the
                # eye-toggle/mask exists to avoid

    def connected_recently(self, now: float) -> bool:
        """True once the success confirmation has been showing long
        enough -- RadarApp uses this to decide when to switch back to the
        radar screen."""
        return (
            self._mode == "result" and self._result_ok
            and self._result_since is not None
            and now - self._result_since >= SUCCESS_DISPLAY_S
        )

    # ---- drawing ----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)
        title = {
            "list": "WLAN", "password": self._selected.ssid if self._selected else "WLAN",
            "connecting": "Verbinde…", "result": "WLAN",
        }.get(self._mode, "WLAN")
        self._draw_header(surface, title)

        if self._mode == "list":
            self._draw_list(surface)
        elif self._mode == "password":
            self._draw_password(surface)
        elif self._mode == "connecting":
            self._draw_connecting(surface)
        elif self._mode == "result":
            self._draw_result(surface)

    def _draw_header(self, surface: pygame.Surface, title: str) -> None:
        top_y = scaling.center_y() - int(scaling.visible_radius() * 0.75)
        cx = scaling.center_x()

        icon_size = scaling.s(TOKENS.icon_medium)
        touch = scaling.s(TOKENS.touch_target)
        arrow_cx = cx - int(scaling.visible_radius() * 0.55)
        arrow_cy = top_y + icon_size // 2
        ui_icons.draw_icon(surface, "chevron-left", (arrow_cx, arrow_cy), icon_size, self.theme.hint)
        self._back_rect = pygame.Rect(0, 0, touch, touch)
        self._back_rect.center = (arrow_cx, arrow_cy)

        title_surf = self._font_title.render(title.upper(), True, self.theme.label)
        surface.blit(title_surf, title_surf.get_rect(midtop=(cx, top_y)))

        self._reload_rect = pygame.Rect(0, 0, 0, 0)
        if self._mode == "list":
            reload_cx = cx + int(scaling.visible_radius() * 0.55)
            colour = self.theme.hint if not self._scanning else self.theme.sweep_colour
            icon = ui_icons.get_icon("refresh-cw", icon_size, colour)
            if self._scanning:
                icon = pygame.transform.rotate(icon, (time.monotonic() * 240) % 360)
            surface.blit(icon, icon.get_rect(center=(reload_cx, arrow_cy)))
            self._reload_rect = pygame.Rect(0, 0, touch, touch)
            self._reload_rect.center = (reload_cx, arrow_cy)

    def _draw_list(self, surface: pygame.Surface) -> None:
        top = nav.content_top_y()
        bottom = nav.content_bottom_y()
        row_h = scaling.s(38)
        gap = scaling.s(1)
        y = top - self._scroll.current_offset()
        total_h = 0
        self._row_rects = []

        if not self._networks and not self._scanning:
            draw_center_text(
                surface, "Keine Netzwerke gefunden", scaling.center_y(), self._font_label, self.theme.hint,
            )
            return

        for net in self._networks:
            if top - row_h <= y <= bottom:
                self._draw_network_row(surface, net, y, row_h)
            if y + row_h >= top and y <= bottom:
                hw = scaling.circle_half_width_at_row(max(y, top), row_h)
                rect = pygame.Rect(scaling.center_x() - hw, y, hw * 2, row_h)
                self._row_rects.append((rect, net))
            y += row_h + gap
            total_h += row_h + gap

        self._scroll.max_offset = max(0, total_h - (bottom - top))
        self._draw_scroll_arc(surface, top, bottom)

    def _draw_network_row(self, surface: pygame.Surface, net: network.NetworkInfo, y: int, row_h: int) -> None:
        hw = scaling.circle_half_width_at_row(y, row_h)
        left = scaling.center_x() - hw
        right = scaling.center_x() + hw
        pad = scaling.s(10)
        colour = self.theme.sweep_colour if net.is_current else self.theme.label

        label_surf = self._font_label.render(net.ssid, True, colour)
        surface.blit(label_surf, (left + pad, y + (row_h - label_surf.get_height()) // 2))

        cy = y + row_h // 2
        bars_right = right - pad
        # Vertically centred on `cy` -- the pre-icon version anchored the
        # bars to the row's top edge `y` instead, a small pre-existing
        # misalignment against the lock icon next to it (fixed in passing).
        used = _draw_signal_icon(surface, bars_right, cy, net.signal, colour)
        if net.secured:
            lock_size = scaling.s(TOKENS.icon_small)
            gap = scaling.s(6)
            ui_icons.draw_icon(
                surface, "lock", (bars_right - used - gap - lock_size // 2, cy), lock_size, self.theme.hint,
            )

        overlay = pygame.Surface((right - left, 1), pygame.SRCALPHA)
        overlay.fill((*self.theme.radar_ring, TOKENS.hairline_alpha))
        surface.blit(overlay, (left, y + row_h))

    def _draw_scroll_arc(self, surface: pygame.Surface, top: int, bottom: int) -> None:
        if self._scroll.max_offset <= 0:
            return
        cx, cy = scaling.center_x(), scaling.center_y()
        r = scaling.visible_radius() - scaling.s(4)
        span = bottom - top
        visible_frac = min(1.0, span / (span + self._scroll.max_offset))
        total_arc = math.radians(40)
        arc_len = max(math.radians(4), total_arc * visible_frac)
        progress = self._scroll.current_offset() / self._scroll.max_offset
        start = math.radians(-20) + (total_arc - arc_len) * progress
        rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        pygame.draw.arc(surface, self.theme.hint, rect, -(start + arc_len), -start, max(1, scaling.s(2)))

    def _draw_password(self, surface: pygame.Surface) -> None:
        cx = scaling.center_x()
        y = int(scaling.visible_radius() * 0.32)

        display_text = self._keyboard.text if not self._masked else "•" * len(self._keyboard.text)
        field_w = scaling.circle_half_width_at_row(y, scaling.s(20)) * 2 - scaling.s(60)
        field_font = self._font_value
        text = fit_text(display_text or "Passwort", field_font, max(20, field_w))
        colour = self.theme.label if self._keyboard.text else self.theme.hint
        rendered = field_font.render(text, True, colour)
        surface.blit(rendered, rendered.get_rect(midtop=(cx, y)))

        eye_size = scaling.s(TOKENS.icon_medium)
        eye_cx = cx + field_w // 2 + scaling.s(20)
        eye_cy = y + rendered.get_height() // 2
        eye_colour = self.theme.sweep_colour if not self._masked else self.theme.hint
        # "eye" while the password is showing, "eye-off" while it's masked
        # -- the earlier version used one glyph shape and only recoloured
        # it, losing that visual distinction.
        eye_icon = "eye" if not self._masked else "eye-off"
        ui_icons.draw_icon(surface, eye_icon, (eye_cx, eye_cy), eye_size, eye_colour)
        touch = scaling.s(TOKENS.touch_target)
        self._eye_rect = pygame.Rect(0, 0, touch, touch)
        self._eye_rect.center = (eye_cx, eye_cy)

        if self._error_message:
            draw_center_text(
                surface, self._error_message, y + rendered.get_height() + scaling.s(10),
                self._font_small, self.theme.emergency,
            )

        self._keyboard.draw(surface)

    def _draw_connecting(self, surface: pygame.Surface) -> None:
        cx, cy = scaling.center_x(), scaling.center_y()
        icon_size = scaling.s(TOKENS.icon_large)
        elapsed = time.monotonic() - self._connect_started_at
        icon = ui_icons.get_icon("loader-circle", icon_size, self.theme.sweep_colour)
        icon = pygame.transform.rotate(icon, (elapsed * 220) % 360)
        surface.blit(icon, icon.get_rect(center=(cx, cy)))

        ssid = self._selected.ssid if self._selected else ""
        draw_center_text(
            surface, f"Verbinde mit {ssid}…", cy + icon_size // 2 + scaling.s(16), self._font_label, self.theme.label,
        )

    def _draw_result(self, surface: pygame.Surface) -> None:
        cy = scaling.center_y()
        if self._result_ok:
            draw_center_text(surface, "Verbunden mit", cy - scaling.s(14), self._font_label, self.theme.muted)
            draw_center_text(surface, self._result_ssid, cy + scaling.s(4), self._font_value, self.theme.sweep_colour)
        else:
            draw_center_text(surface, "Verbindung fehlgeschlagen", cy - scaling.s(14), self._font_label, self.theme.label)
            if self._error_message:
                draw_center_text(surface, self._error_message, cy + scaling.s(10), self._font_small, self.theme.hint)

    # ---- input --------------------------------------------------------

    def handle_tap(self, x: int, y: int) -> str:
        if self._back_rect.collidepoint(x, y):
            return self._go_back()

        if self._mode == "list":
            if self._reload_rect.collidepoint(x, y):
                self.start_scan()
                return ""
            for rect, net in self._row_rects:
                if rect.collidepoint(x, y):
                    return self._select_network(net)
            return ""

        if self._mode == "password":
            if self._eye_rect.collidepoint(x, y):
                self._masked = not self._masked
                return ""
            result = self._keyboard.handle_tap(x, y)
            if result == "ok" and self._keyboard.text:
                self._error_message = None
                self._start_connect(self._selected.ssid, self._keyboard.text)
            return ""

        return ""

    def handle_scroll(self, direction: int) -> None:
        if self._mode == "list":
            self._scroll.kick(direction * scaling.s(60))

    def _select_network(self, net: network.NetworkInfo) -> str:
        self._selected = net
        self._error_message = None
        if net.secured:
            self._mode = "password"
            self._masked = True
            self._keyboard.reset()
        else:
            self._start_connect(net.ssid, None)
        return ""

    def _go_back(self) -> str:
        if self._mode in ("password", "connecting"):
            self._mode = "list"
            self._keyboard.reset()
            self._selected = None
            self._error_message = None
            return ""
        if self._mode == "result" and not self._result_ok:
            self._mode = "list"
            return ""
        return "radar"

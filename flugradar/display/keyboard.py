"""Bildschirmtastatur für Texteingabe auf dem Rundtouch-Display.

Es gab dafür noch keine Komponente im Projekt -- gebraucht für die
WLAN-Passworteingabe (flugradar/display/screens/wifi.py), aber bewusst
eigenständig und wiederverwendbar gehalten.

QWERTZ-Layout als Default: alle übrigen UI-Texte im Projekt sind Deutsch
(siehe menu.py etc.), und die Zielgruppe tippt an einem deutschen Gerät --
QWERTY hätte an dieser einen Stelle unnötig einen anderen Tastenlayout-
Habit erzwungen als jede physische Tastatur, die die Nutzer sonst kennen.

Passt sich der Kreisgeometrie an: jede Reihe fragt ihre tatsächlich
nutzbare Sehnenbreite über scaling.circle_half_width_at_row() ab (gleiches
Prinzip wie die Menü-Zeilen in menu.py) und verteilt ihre Tasten
proportional zu deren Gewicht (Leertaste/Bestätigen breiter als ein
einzelner Buchstabe) darauf -- eine feste Pixel-Breite pro Taste würde am
oberen/unteren Rand des Kreises abgeschnitten.
"""

from __future__ import annotations

from typing import Optional

import pygame

from flugradar.display import scaling
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme

_LETTER_ROWS = ("qwertzuiop", "asdfghjkl", "yxcvbnm")
_SYMBOL_ROWS = ("1234567890", "-_.:/\\@#!?", "+=*&%()")

_SPECIAL_WEIGHTS = {
    "shift": 1.6, "back": 1.6, "123": 1.6, "ABC": 1.6,
    "space": 4.0, "ok": 2.4,
}

_LABELS = {
    "shift": "⇧", "back": "⌫", "space": "␣", "ok": "OK",
    "123": "123", "ABC": "ABC",
}


def _weight(key: str) -> float:
    return _SPECIAL_WEIGHTS.get(key, 1.0)


class OnScreenKeyboard:
    """Self-contained text-entry widget: owns its own text buffer plus
    shift/symbol-layer state, and its own hit-testing. `handle_tap`
    returns "ok" once the confirm key is tapped, "" otherwise (same
    convention as MenuScreen.handle_tap)."""

    def __init__(self, screen_size: int, theme: Theme) -> None:
        self.size = screen_size
        self.theme = theme
        self.text = ""
        self._shift = False
        self._symbols = False
        self._key_rects: list[tuple[pygame.Rect, str]] = []
        self._fonts_ready = False
        self._font_key: Optional[pygame.font.Font] = None

    def reset(self) -> None:
        self.text = ""
        self._shift = False
        self._symbols = False

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._font_key = get_font(scaling.s(TOKENS.font_standard), bold=True)
            self._fonts_ready = True

    def _rows(self) -> list[list[str]]:
        letters = _SYMBOL_ROWS if self._symbols else _LETTER_ROWS
        upper = self._shift and not self._symbols
        row1 = list(letters[0].upper() if upper else letters[0])
        row2 = list(letters[1].upper() if upper else letters[1])
        row3_mid = list(letters[2].upper() if upper else letters[2])
        row3_prefix = "ABC" if self._symbols else "shift"
        row4_prefix = "123"
        return [
            row1,
            row2,
            [row3_prefix, *row3_mid, "back"],
            [row4_prefix, "space", "ok"],
        ]

    def top_y(self) -> int:
        """Lower ~55% of the visible circle -- a full keyboard row doesn't
        fit near the very top/bottom of a round panel, so the block stays
        clear of both edges."""
        return scaling.center_y() + int(scaling.visible_radius() * 0.05)

    def row_height(self) -> int:
        return scaling.s(34)

    def bottom_y(self) -> int:
        row_h = self.row_height()
        gap = scaling.s(4)
        return self.top_y() + 4 * (row_h + gap)

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        self._key_rects = []
        row_h = self.row_height()
        gap = scaling.s(4)
        key_gap = scaling.s(3)
        y = self.top_y()

        for row in self._rows():
            hw = scaling.circle_half_width_at_row(y, row_h)
            left = scaling.center_x() - hw
            right = scaling.center_x() + hw
            total_w = right - left
            weights = [_weight(k) for k in row]
            weight_sum = sum(weights) or 1.0
            usable = max(0, total_w - key_gap * (len(row) - 1))
            x = left
            for key, w in zip(row, weights):
                kw = max(1, int(usable * (w / weight_sum)))
                rect = pygame.Rect(x, y, kw, row_h)
                self._draw_key(surface, rect, key)
                self._key_rects.append((rect, key))
                x += kw + key_gap
            y += row_h + gap

    def _is_active_toggle(self, key: str) -> bool:
        if key == "shift":
            return self._shift
        if key == "123":
            return self._symbols
        return False

    def _draw_key(self, surface: pygame.Surface, rect: pygame.Rect, key: str) -> None:
        active = self._is_active_toggle(key)
        fill = self.theme.surface_accent if active else self.theme.surface
        pygame.draw.rect(surface, fill, rect, border_radius=scaling.s(6))
        label = _LABELS.get(key, key)
        text_color = self.theme.sweep_colour if (key == "ok" or active) else self.theme.label
        rendered = self._font_key.render(label, True, text_color)
        surface.blit(rendered, rendered.get_rect(center=rect.center))

    def handle_tap(self, x: int, y: int) -> str:
        for rect, key in self._key_rects:
            if not rect.collidepoint(x, y):
                continue
            return self._activate(key)
        return ""

    def _activate(self, key: str) -> str:
        if key == "shift":
            self._shift = not self._shift
            return ""
        if key == "123":
            self._symbols = True
            self._shift = False
            return ""
        if key == "ABC":
            self._symbols = False
            return ""
        if key == "back":
            self.text = self.text[:-1]
            return ""
        if key == "space":
            self.text += " "
            return ""
        if key == "ok":
            return "ok"
        self.text += key
        if self._shift and not self._symbols:
            self._shift = False  # one-shot shift, like a phone keyboard
        return ""

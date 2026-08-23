"""ListRow component (Schritt 2 of the UI overhaul).

Generalises the row-drawing that currently lives inline in
`screens/menu.py::MenuScreen._draw_row` (label left, value right dimmed,
optional leading icon, optional trailing chevron, hairline divider ending
at the chord) into a reusable, chord-aware, tap-animated component.

Not wired into menu.py yet -- migrating its settings rows onto this is
Schritt 4 ("Einstellungsmenue auf ListRow/Toggle/Segmented/Slider
umstellen"). Built now, with its own tests, so that migration is a
straight swap instead of also having to design the component under time
pressure then.
"""

from __future__ import annotations

from typing import Optional

import pygame

from flugradar.display import scaling, ui_icons
from flugradar.display.draw_helpers import fit_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme, blend
from flugradar.display.ui.tap_feedback import TapFeedback


class ListRow:
    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._feedback = TapFeedback()
        self._rect = pygame.Rect(0, 0, 0, 0)
        self._fonts_ready = False
        self._label_font: Optional[pygame.font.Font] = None
        self._value_font: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._label_font = get_font(scaling.s(TOKENS.font_standard))
            self._value_font = get_font(scaling.s(TOKENS.font_value), mono=True)
            self._fonts_ready = True

    @staticmethod
    def height() -> int:
        return scaling.s(TOKENS.touch_target)

    def draw(
        self,
        surface: pygame.Surface,
        y: int,
        label: str,
        value: str = "",
        icon: Optional[str] = None,
        chevron: bool = False,
        enabled: bool = True,
    ) -> None:
        self._ensure_fonts()
        row_h = self.height()
        hw = scaling.circle_half_width_at_row(y, row_h)
        left = scaling.center_x() - hw
        right = scaling.center_x() + hw
        self._rect = pygame.Rect(left, y, right - left, row_h)
        pad = scaling.s(10)

        flash = self._feedback.brightness()
        label_colour = self.theme.label if enabled else self.theme.hint
        value_colour = self.theme.sweep_colour if enabled else self.theme.hint
        if flash:
            label_colour = blend(label_colour, self.theme.sweep_colour, flash * 0.5)

        x = left + pad
        if icon:
            icon_size = scaling.s(TOKENS.icon_small)
            ui_icons.draw_icon(surface, icon, (x + icon_size // 2, y + row_h // 2), icon_size, label_colour)
            x += icon_size + scaling.s(6)

        label_surf = self._label_font.render(label, True, label_colour)
        surface.blit(label_surf, (x, y + (row_h - label_surf.get_height()) // 2))

        right_edge = right - pad
        if chevron:
            chevron_size = scaling.s(TOKENS.icon_small)
            ui_icons.draw_icon(
                surface, "chevron-right", (right_edge - chevron_size // 2, y + row_h // 2),
                chevron_size, self.theme.hint,
            )
            right_edge -= chevron_size + scaling.s(4)

        if value:
            max_val_w = max(0, right_edge - (x + label_surf.get_width() + scaling.s(6)))
            text = fit_text(value, self._value_font, max_val_w)
            value_surf = self._value_font.render(text, True, value_colour)
            surface.blit(value_surf, (right_edge - value_surf.get_width(), y + (row_h - value_surf.get_height()) // 2))

        overlay = pygame.Surface((right - left, 1), pygame.SRCALPHA)
        overlay.fill((*self.theme.radar_ring, TOKENS.hairline_alpha))
        surface.blit(overlay, (left, y + row_h))

    def handle_tap(self, x: int, y: int) -> bool:
        if self._rect.collidepoint(x, y):
            self._feedback.trigger()
            return True
        return False

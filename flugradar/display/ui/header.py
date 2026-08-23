"""Header component (Schritt 2 of the UI overhaul).

Title plus an optional back chevron, meant to replace the breadcrumb
chain (`nav.draw_breadcrumb`): a three-level trail like "Radar > Flight >
DLH400" is too much text for too little information on a 4" round panel,
a title plus a back icon reads at a glance from across the room.

Not wired into any screen yet -- that happens in Schritt 4 together with
the navigation-model rework (Schritt 3), which is what actually removes
the need for a multi-level trail in the first place. Built now so it's
ready, and to prove the component shape (theme in, TOKENS-driven sizing,
tap feedback, chord-independent since it doesn't need the chord) works
before every screen depends on it.
"""

from __future__ import annotations

from typing import Optional

import pygame

from flugradar.display import scaling, ui_icons
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme, blend
from flugradar.display.ui.tap_feedback import TapFeedback


class Header:
    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._back_feedback = TapFeedback()
        self._back_rect = pygame.Rect(0, 0, 0, 0)
        self._title_font: Optional[pygame.font.Font] = None

    def _ensure_font(self) -> None:
        if self._title_font is None:
            self._title_font = get_font(scaling.s(TOKENS.font_title), bold=True)

    def draw(self, surface: pygame.Surface, title: str, show_back: bool = True) -> None:
        self._ensure_font()
        top_y = scaling.center_y() - int(scaling.visible_radius() * 0.75)
        cx = scaling.center_x()

        title_surf = self._title_font.render(title.upper(), True, self.theme.label)
        surface.blit(title_surf, title_surf.get_rect(midtop=(cx, top_y)))

        self._back_rect = pygame.Rect(0, 0, 0, 0)
        if not show_back:
            return

        icon_size = scaling.s(TOKENS.icon_medium)
        back_cx = cx - int(scaling.visible_radius() * 0.55)
        back_cy = top_y + icon_size // 2
        flash = self._back_feedback.brightness()
        colour = blend(self.theme.hint, self.theme.sweep_colour, flash) if flash else self.theme.hint
        ui_icons.draw_icon(surface, "chevron-left", (back_cx, back_cy), icon_size, colour)

        touch = scaling.s(TOKENS.touch_target)
        self._back_rect = pygame.Rect(0, 0, touch, touch)
        self._back_rect.center = (back_cx, back_cy)

    def handle_tap(self, x: int, y: int) -> bool:
        if self._back_rect.collidepoint(x, y):
            self._back_feedback.trigger()
            return True
        return False

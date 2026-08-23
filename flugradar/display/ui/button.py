"""Button component (Schritt 2 of the UI overhaul) -- the footer action button.

Today's footer button is a filled rectangle + border + icon + upper-case
label -- three emphasis devices stacked on very little space. The brief
asks for both that look and a flatter alternative to be built and
compared as screenshots before picking one (Rueckfrage: "Footer-Buttons:
mit oder ohne Flaeche"), so this component supports both via `variant`:

- "filled": today's look, ported onto TOKENS/tap-feedback unchanged
  visually.
- "flat": icon + label in the accent colour, no box; only the primary
  action (accent=True, e.g. the "radar" button) keeps a filled pill --
  everything else is unboxed.

`nav.draw_footer_buttons` is the first consumer (Schritt 2's hardening
pass); it currently defaults to "flat" per the brief's own suggestion,
pending the user's screenshot comparison and decision.
"""

from __future__ import annotations

from typing import Optional

import pygame

from flugradar.display import scaling, ui_icons
from flugradar.display.draw_helpers import fit_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme, blend
from flugradar.display.ui.tap_feedback import TapFeedback

VARIANTS = ("filled", "flat")


class Button:
    def __init__(self, theme: Theme, variant: str = "flat") -> None:
        if variant not in VARIANTS:
            raise ValueError(f"unknown Button variant {variant!r}, expected one of {VARIANTS}")
        self.theme = theme
        self.variant = variant
        self._feedback = TapFeedback()
        self._rect = pygame.Rect(0, 0, 0, 0)
        self._label_font: Optional[pygame.font.Font] = None

    def _ensure_font(self) -> None:
        if self._label_font is None:
            self._label_font = get_font(scaling.s(TOKENS.font_standard))

    def draw(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        icon: Optional[str],
        label: str,
        accent: bool = False,
    ) -> None:
        self._ensure_font()
        self._rect = rect
        flash = self._feedback.brightness()

        icon_colour = self.theme.sweep_colour if accent else self.theme.label
        label_colour = self.theme.sweep_colour if accent else self.theme.hint

        filled = self.variant == "filled" or accent
        if filled:
            fill = self.theme.surface_accent if accent else self.theme.surface
            border = self.theme.sweep_colour if accent else self.theme.radar_ring
            if flash:
                fill = blend(fill, self.theme.sweep_colour, flash * 0.35)
            radius = max(scaling.s(8), rect.height // 4)
            width = max(1, scaling.s(TOKENS.line_stroke) if accent else scaling.s(TOKENS.line_stroke // 2))
            pygame.draw.rect(surface, fill, rect, border_radius=radius)
            pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)
        elif flash:
            icon_colour = blend(icon_colour, self.theme.sweep_colour, flash)
            label_colour = blend(label_colour, self.theme.sweep_colour, flash)

        icon_cy = rect.centery - scaling.s(6)
        icon_size = scaling.s(TOKENS.icon_medium)
        if icon:
            ui_icons.draw_icon(surface, icon, (rect.centerx, icon_cy), icon_size, icon_colour)

        text = fit_text(label, self._label_font, rect.width - scaling.s(6))
        rendered = self._label_font.render(text, True, label_colour)
        surface.blit(rendered, rendered.get_rect(midtop=(rect.centerx, icon_cy + scaling.s(10))))

    def handle_tap(self, x: int, y: int) -> bool:
        if self._rect.collidepoint(x, y):
            self._feedback.trigger()
            return True
        return False

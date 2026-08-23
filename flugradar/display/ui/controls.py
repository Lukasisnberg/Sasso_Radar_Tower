"""Toggle / Segmented / Slider / Confirm controls (Schritt 2 of the UI overhaul).

The on-device settings menu (`screens/menu.py`) currently renders all four
of its widget kinds (Umschalter/Einfachauswahl/Stufenregler/Aktion-mit-
Rueckfrage) as plain text or ad-hoc lines drawn inline in `_draw_row`/
`_draw_slider_track`. These four classes are the real, chord-independent
building blocks meant to replace that -- not wired into menu.py yet
(Schritt 4), so their geometry is deliberately self-contained (a caller
just gives a centre point or a rect, not the row-layout maths menu.py
does today).

Each control owns no state beyond its tap-feedback flash; the caller
supplies the current value on every draw() call and reacts to what
handle_tap() reports.
"""

from __future__ import annotations

from typing import Optional

import pygame

from flugradar.display import scaling
from flugradar.display.draw_helpers import fit_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme, blend
from flugradar.display.ui.tap_feedback import TapFeedback

# Reference-px geometry local to Toggle -- not promoted to TOKENS since
# nothing else in the app needs a switch-track size (same convention as
# other screens' small local sizing constants, e.g. weather.py's
# _HERO_TEMP_SCALE).
_TOGGLE_W = 32
_TOGGLE_H = 18
_TOGGLE_PAD = 2


class Toggle:
    """Flat pill switch. Tapping anywhere in its touch target requests a
    flip -- the caller owns the actual boolean and passes the current
    value in each draw() call."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._feedback = TapFeedback()
        self._rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface: pygame.Surface, center: tuple[int, int], value: bool, enabled: bool = True) -> None:
        w, h = scaling.s(_TOGGLE_W), scaling.s(_TOGGLE_H)
        pad = scaling.s(_TOGGLE_PAD)
        track = pygame.Rect(0, 0, w, h)
        track.center = center

        on_colour = self.theme.sweep_colour if enabled else self.theme.hint
        track_colour = on_colour if value else self.theme.radar_ring
        flash = self._feedback.brightness()
        if flash:
            track_colour = blend(track_colour, self.theme.sweep_colour, flash * 0.4)
        pygame.draw.rect(surface, track_colour, track, border_radius=h // 2)

        thumb_r = max(1, (h - pad * 2) // 2)
        thumb_x = track.right - pad - thumb_r if value else track.left + pad + thumb_r
        pygame.draw.circle(surface, self.theme.background, (thumb_x, center[1]), thumb_r)

        touch = scaling.s(TOKENS.touch_target)
        self._rect = pygame.Rect(0, 0, max(touch, w), max(touch, h))
        self._rect.center = center

    def handle_tap(self, x: int, y: int) -> bool:
        if self._rect.collidepoint(x, y):
            self._feedback.trigger()
            return True
        return False


class Segmented:
    """Single-choice control with up to a handful of options shown side by
    side within a caller-supplied rect (Rahmenbedingungen: <=3 options
    visible at once, so the user picks directly instead of cycling)."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._feedback = TapFeedback()
        self._option_rects: list[pygame.Rect] = []
        self._font: Optional[pygame.font.Font] = None

    def _ensure_font(self) -> None:
        if self._font is None:
            self._font = get_font(scaling.s(TOKENS.font_standard))

    def draw(self, surface: pygame.Surface, rect: pygame.Rect, options: list[str], selected_index: int) -> None:
        self._ensure_font()
        n = len(options)
        self._option_rects = []
        if n == 0:
            return
        seg_w = rect.width // n
        radius = scaling.s(6)
        flash = self._feedback.brightness()

        pygame.draw.rect(surface, self.theme.surface, rect, border_radius=radius)
        for i, label in enumerate(options):
            seg_rect = pygame.Rect(rect.left + i * seg_w, rect.top, seg_w, rect.height)
            if i == n - 1:
                seg_rect.width = rect.right - seg_rect.left
            self._option_rects.append(seg_rect)

            selected = i == selected_index
            if selected:
                fill = self.theme.surface_accent
                if flash:
                    fill = blend(fill, self.theme.sweep_colour, flash * 0.35)
                inset = seg_rect.inflate(-scaling.s(2), -scaling.s(2))
                pygame.draw.rect(surface, fill, inset, border_radius=max(2, radius - scaling.s(2)))

            colour = self.theme.sweep_colour if selected else self.theme.hint
            text = fit_text(label, self._font, seg_rect.width - scaling.s(4))
            text_surf = self._font.render(text, True, colour)
            surface.blit(text_surf, text_surf.get_rect(center=seg_rect.center))

    def handle_tap(self, x: int, y: int) -> Optional[int]:
        for i, r in enumerate(self._option_rects):
            if r.collidepoint(x, y):
                self._feedback.trigger()
                return i
        return None


class Slider:
    """Thin-line stepper track with an accent handle at the fill point,
    replacing menu.py's plain two-colour line (`_draw_slider_track`)."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._feedback = TapFeedback()
        self._rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface: pygame.Surface, x0: int, x1: int, y: int, fraction: float, enabled: bool = True) -> None:
        fraction = max(0.0, min(1.0, fraction))
        track_h = max(2, scaling.s(TOKENS.line_stroke))
        pygame.draw.line(surface, self.theme.radar_ring, (x0, y), (x1, y), track_h)

        colour = self.theme.sweep_colour if enabled else self.theme.hint
        fill_x = x0 + int((x1 - x0) * fraction)
        pygame.draw.line(surface, colour, (x0, y), (fill_x, y), track_h)

        flash = self._feedback.brightness()
        handle_colour = blend(colour, self.theme.label, flash * 0.5) if flash else colour
        handle_r = max(2, scaling.s(TOKENS.icon_small) // 3)
        pygame.draw.circle(surface, handle_colour, (fill_x, y), handle_r)

        touch = scaling.s(TOKENS.touch_target)
        self._rect = pygame.Rect(min(x0, x1), y - touch // 2, abs(x1 - x0), touch)

    def handle_tap(self, x: int, y: int) -> Optional[float]:
        """Returns the tapped fraction (0..1) along the track, or None if
        the tap missed. Slider doesn't know the value's own min/max/step
        -- the caller maps the fraction back to its own domain."""
        if not self._rect.collidepoint(x, y):
            return None
        self._feedback.trigger()
        x0, x1 = self._rect.left, self._rect.right
        if x1 <= x0:
            return 0.0
        return max(0.0, min(1.0, (x - x0) / (x1 - x0)))


class Confirm:
    """Two-button confirm/cancel row, replacing the split-tap-by-midpoint
    pattern `screens/menu.py` currently uses for its "action" rows."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._confirm_feedback = TapFeedback()
        self._cancel_feedback = TapFeedback()
        self._confirm_rect = pygame.Rect(0, 0, 0, 0)
        self._cancel_rect = pygame.Rect(0, 0, 0, 0)
        self._fonts_ready = False
        self._label_font: Optional[pygame.font.Font] = None
        self._hint_font: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._label_font = get_font(scaling.s(TOKENS.font_standard))
            self._hint_font = get_font(scaling.s(TOKENS.font_small))
            self._fonts_ready = True

    def draw(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        confirm_label: str = "Bestätigen",
        cancel_label: str = "Abbrechen",
        hint_lines: Optional[list[str]] = None,
    ) -> None:
        self._ensure_fonts()
        top = rect.top
        if hint_lines:
            for line in hint_lines:
                hint_surf = self._hint_font.render(line, True, self.theme.hint)
                surface.blit(hint_surf, hint_surf.get_rect(midtop=(rect.centerx, top)))
                top += hint_surf.get_height() + scaling.s(2)
            top += scaling.s(4)

        btn_h = max(1, rect.bottom - top)
        gap = scaling.s(4)
        mid = rect.centerx
        self._confirm_rect = pygame.Rect(rect.left, top, mid - rect.left - gap // 2, btn_h)
        self._cancel_rect = pygame.Rect(mid + gap // 2, top, rect.right - mid - gap // 2, btn_h)

        radius = scaling.s(6)
        for r, feedback, base_fill, label, colour in (
            (self._confirm_rect, self._confirm_feedback, self.theme.surface_accent, confirm_label, self.theme.sweep_colour),
            (self._cancel_rect, self._cancel_feedback, self.theme.surface, cancel_label, self.theme.muted),
        ):
            fill = base_fill
            flash = feedback.brightness()
            if flash:
                fill = blend(fill, self.theme.sweep_colour, flash * 0.3)
            pygame.draw.rect(surface, fill, r, border_radius=radius)
            text_surf = self._label_font.render(label, True, colour)
            surface.blit(text_surf, text_surf.get_rect(center=r.center))

    def handle_tap(self, x: int, y: int) -> Optional[str]:
        if self._confirm_rect.collidepoint(x, y):
            self._confirm_feedback.trigger()
            return "confirm"
        if self._cancel_rect.collidepoint(x, y):
            self._cancel_feedback.trigger()
            return "cancel"
        return None

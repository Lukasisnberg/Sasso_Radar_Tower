"""Navigation chrome — breadcrumbs, page dots, footer buttons."""

from __future__ import annotations

import pygame

import time

from flugradar.display import scaling, ui_icons
from flugradar.display.draw_helpers import fit_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme, ease_out_cubic

# How long a single momentum-scroll "kick" (nav.ScrollState.kick) takes to
# settle -- long end of the two animation-duration tokens, since it's a
# content move rather than tap feedback.
_COAST_DURATION_S = TOKENS.duration_long_ms / 1000.0


class ScrollState:
    def __init__(self) -> None:
        self.offset = 0
        self.max_offset = 0
        self._anim_from = 0
        self._anim_to = 0
        self._anim_start = 0.0

    def reset(self) -> None:
        self.offset = 0
        self.max_offset = 0
        self._anim_from = 0
        self._anim_to = 0
        self._anim_start = 0.0

    def clamp(self) -> None:
        self.offset = max(0, min(self.offset, self.max_offset))

    def step(self, delta: int) -> None:
        self.offset += delta
        self.clamp()

    def kick(self, delta: int) -> None:
        """Start an eased coast-to-stop scroll of `delta` px from wherever
        the view currently is (mid-coast or at rest) -- used by screens
        that want 'Nachlauf und weiches Abbremsen' from a discrete swipe
        instead of an instant jump (nav.ScrollState.step)."""
        self._anim_from = self.current_offset()
        target = max(0, min(self._anim_from + delta, self.max_offset))
        self._anim_to = target
        self._anim_start = time.monotonic()

    def current_offset(self) -> int:
        if self._anim_from == self._anim_to:
            return self._anim_to
        t = (time.monotonic() - self._anim_start) / _COAST_DURATION_S
        if t >= 1.0:
            self._anim_from = self._anim_to
            return self._anim_to
        eased = ease_out_cubic(t)
        return int(round(self._anim_from + (self._anim_to - self._anim_from) * eased))


def _top_y() -> int:
    return scaling.center_y() - int(scaling.visible_radius() * 0.75)


def _footer_top_y() -> int:
    return scaling.center_y() + int(scaling.visible_radius() * 0.68)


def content_top_y(has_dots: bool = False) -> int:
    if has_dots:
        return _top_y() + scaling.s(28) + scaling.s(10)
    return _top_y() + scaling.s(36)


def content_bottom_y() -> int:
    return _footer_top_y() - scaling.s(10)


def _max_text_width(y: int, font_height: int) -> int:
    return max(40, scaling.circle_half_width_at_row(y, font_height) * 2 - scaling.s(8))


def _fit_breadcrumb_parts(
    parts: list[str], font: pygame.font.Font, max_w: int
) -> list[str]:
    sep = " › "
    if not parts:
        return parts
    for start in range(len(parts)):
        trial = parts[start:]
        while trial:
            line = sep.join(trial)
            if font.size(line)[0] <= max_w:
                return trial
            if len(trial) <= 1:
                return [fit_text(trial[0], font, max_w)]
            trial = trial[1:]
    return [fit_text(parts[-1], font, max_w)]


def draw_breadcrumb(
    surface: pygame.Surface,
    parts: list[str],
    theme: Theme,
) -> None:
    if not parts:
        return
    font = get_font(scaling.s(TOKENS.font_title))
    sep_str = " › "
    sep_surf = font.render(sep_str, True, theme.hint)
    y = _top_y()
    h = font.get_height()
    max_w = _max_text_width(y, h)
    display = _fit_breadcrumb_parts(parts, font, max_w)

    rendered = []
    total_w = 0
    for i, part in enumerate(display):
        color = theme.sweep_colour if i == len(display) - 1 else theme.muted
        used = total_w + (sep_surf.get_width() if rendered else 0)
        remaining = max(20, max_w - used)
        text = fit_text(part, font, remaining)
        img = font.render(text, True, color)
        rendered.append(img)
        total_w += img.get_width()
        if i < len(display) - 1:
            total_w += sep_surf.get_width()

    if total_w > max_w:
        line = fit_text(sep_str.join(parts), font, max_w)
        img = font.render(line, True, theme.muted)
        surface.blit(img, img.get_rect(midtop=(scaling.center_x(), y)))
        return

    x = scaling.center_x() - total_w // 2
    for i, img in enumerate(rendered):
        surface.blit(img, (x, y))
        x += img.get_width()
        if i < len(rendered) - 1:
            surface.blit(sep_surf, (x, y))
            x += sep_surf.get_width()


def draw_page_dots(
    surface: pygame.Surface,
    active: int,
    total: int,
    theme: Theme,
) -> None:
    if total <= 1:
        return
    y = _top_y() + scaling.s(30)
    gap = scaling.s(14)
    r = max(2, scaling.s(4))
    span = (total - 1) * gap
    x0 = scaling.center_x() - span // 2
    for i in range(total):
        cx = x0 + i * gap
        color = theme.sweep_colour if i == active else theme.page_dot_inactive
        pygame.draw.circle(surface, color, (cx, y), r)


def footer_button_rects(button_count: int) -> list[pygame.Rect]:
    if button_count <= 0:
        return []
    btn_h = scaling.s(40)
    gap = scaling.s(10)
    center_y = scaling.center_y() + int(scaling.visible_radius() * 0.71)
    pad = scaling.s(6)
    y = center_y - btn_h // 2 - pad // 2

    max_w = _max_text_width(y + btn_h // 2, btn_h)
    total_gap = gap * max(0, button_count - 1)
    btn_w = (max_w - total_gap) // button_count
    btn_w = min(btn_w, scaling.s(78))
    total_w = btn_w * button_count + total_gap
    x0 = scaling.center_x() - total_w // 2
    return [
        pygame.Rect(x0 + i * (btn_w + gap), y, btn_w, btn_h)
        for i in range(button_count)
    ]


def draw_footer_buttons(
    surface: pygame.Surface,
    kinds: list[str],
    theme: Theme,
) -> None:
    if not kinds:
        return
    rects = footer_button_rects(len(kinds))
    btn_fill = theme.surface
    btn_fill_accent = theme.surface_accent
    btn_border = theme.radar_ring
    btn_border_accent = theme.sweep_colour

    for kind, rect in zip(kinds, rects):
        accent = kind == "radar"
        fill = btn_fill_accent if accent else btn_fill
        border = btn_border_accent if accent else btn_border
        radius = max(scaling.s(8), rect.height // 4)
        width = max(1, scaling.s(TOKENS.line_stroke) if accent else scaling.s(TOKENS.line_stroke // 2))

        pygame.draw.rect(surface, fill, rect, border_radius=radius)
        pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)

        icon_color = theme.sweep_colour if accent else theme.label
        icon_cy = rect.centery - scaling.s(6)
        icon_size = scaling.s(TOKENS.icon_medium)

        if kind == "prev":
            ui_icons.draw_icon(surface, "chevron-left", (rect.centerx, icon_cy), icon_size, icon_color)
        elif kind == "next":
            ui_icons.draw_icon(surface, "chevron-right", (rect.centerx, icon_cy), icon_size, icon_color)
        elif kind == "radar":
            ui_icons.draw_icon(surface, "radar", (rect.centerx, icon_cy), icon_size, icon_color)

        labels = {
            "prev": "ZURÜCK", "next": "WEITER", "radar": "RADAR",
            "track": "FOLGEN", "untrack": "STOPP", "stop": "STOPP",
        }
        label = labels.get(kind, kind.upper())
        label_font = get_font(scaling.s(TOKENS.font_standard))
        label_color = theme.sweep_colour if accent else theme.hint
        text = fit_text(label, label_font, rect.width - scaling.s(6))
        rendered = label_font.render(text, True, label_color)
        surface.blit(rendered, rendered.get_rect(midtop=(rect.centerx, icon_cy + scaling.s(10))))


def tap_footer_button(
    x: int,
    y: int,
    button_count: int,
) -> int | None:
    rects = footer_button_rects(button_count)
    for i, rect in enumerate(rects):
        if rect.collidepoint(x, y):
            return i
    return None

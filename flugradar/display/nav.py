"""Navigation chrome — breadcrumbs, page dots, footer buttons."""

from __future__ import annotations

import math

import pygame

from flugradar.display import scaling
from flugradar.display.draw_helpers import fit_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import Theme


class ScrollState:
    def __init__(self) -> None:
        self.offset = 0
        self.max_offset = 0

    def reset(self) -> None:
        self.offset = 0
        self.max_offset = 0

    def clamp(self) -> None:
        self.offset = max(0, min(self.offset, self.max_offset))

    def step(self, delta: int) -> None:
        self.offset += delta
        self.clamp()


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
    font = get_font(scaling.s(14))
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


def _draw_nav_arrow(
    surface: pygame.Surface,
    center: tuple[int, int],
    size: int,
    color: tuple[int, int, int],
    left: bool,
) -> None:
    cx, cy = center
    half_h = size
    reach = size + scaling.s(2)
    if left:
        pts = [(cx - reach, cy), (cx + reach // 2, cy - half_h), (cx + reach // 2, cy + half_h)]
    else:
        pts = [(cx + reach, cy), (cx - reach // 2, cy - half_h), (cx - reach // 2, cy + half_h)]
    pygame.draw.polygon(surface, color, pts)


def _draw_radar_icon(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    theme: Theme,
) -> None:
    cx, cy = center
    r = max(4, radius)
    grid_color = theme.radar_ring
    pygame.draw.circle(surface, color, (cx, cy), r, max(1, scaling.s(2)))
    pygame.draw.circle(surface, grid_color, (cx, cy), max(2, r * 2 // 3), 1)
    pygame.draw.line(surface, grid_color, (cx - r, cy), (cx + r, cy), 1)
    pygame.draw.line(surface, grid_color, (cx, cy - r), (cx, cy + r), 1)
    sweep_rad = math.radians(-35)
    sx = cx + int(r * math.cos(sweep_rad))
    sy = cy + int(r * math.sin(sweep_rad))
    pygame.draw.line(surface, theme.sweep_colour, (cx, cy), (sx, sy), max(2, scaling.s(2)))
    pygame.draw.circle(surface, theme.aircraft_dot, (cx + r // 3, cy - r // 4), max(2, scaling.s(3)))


def draw_footer_buttons(
    surface: pygame.Surface,
    kinds: list[str],
    theme: Theme,
) -> None:
    if not kinds:
        return
    rects = footer_button_rects(len(kinds))
    btn_fill = (8, 38, 14)
    btn_fill_accent = (12, 52, 22)
    btn_border = theme.radar_ring
    btn_border_accent = theme.sweep_colour

    for kind, rect in zip(kinds, rects):
        accent = kind == "radar"
        fill = btn_fill_accent if accent else btn_fill
        border = btn_border_accent if accent else btn_border
        radius = max(scaling.s(8), rect.height // 4)
        width = max(1, scaling.s(2) if accent else scaling.s(1))

        pygame.draw.rect(surface, fill, rect, border_radius=radius)
        pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)

        icon_color = theme.sweep_colour if accent else theme.label
        icon_cy = rect.centery - scaling.s(6)
        icon_size = scaling.s(7)

        if kind == "prev":
            _draw_nav_arrow(surface, (rect.centerx, icon_cy), icon_size, icon_color, left=True)
        elif kind == "next":
            _draw_nav_arrow(surface, (rect.centerx, icon_cy), icon_size, icon_color, left=False)
        elif kind == "radar":
            _draw_radar_icon(surface, (rect.centerx, icon_cy), icon_size, icon_color, theme)

        labels = {"prev": "PREV", "next": "NEXT", "radar": "RADAR"}
        label = labels.get(kind, kind.upper())
        label_font = get_font(scaling.s(11))
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

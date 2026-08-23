"""Scroll chrome shared across screens (Schritt 2 of the UI overhaul).

Unlike every other component in this package, these stay plain functions:
a page-dots row and a scroll-position arc are purely a function of
state the caller already owns (current scroll offset/max, active
page/page count) -- there is no independent animation progress of their
own to track, so a stateful component class would carry nothing.

`draw_scroll_arc` replaces two near-identical `_draw_scroll_arc` methods
that used to live separately in menu.py and wifi.py (flagged as a
duplicate in docs/ui-inventar.md); `draw_page_dots` is exactly the pixel
math nav.draw_page_dots already had, just relocated here with nav.py
re-exporting it unchanged for its one external caller (detail.py).
"""

from __future__ import annotations

import math

import pygame

from flugradar.display import scaling
from flugradar.display.theme import Theme


def draw_page_dots(surface: pygame.Surface, active: int, total: int, theme: Theme, y: int) -> None:
    if total <= 1:
        return
    gap = scaling.s(14)
    r = max(2, scaling.s(4))
    span = (total - 1) * gap
    x0 = scaling.center_x() - span // 2
    for i in range(total):
        cx = x0 + i * gap
        color = theme.sweep_colour if i == active else theme.page_dot_inactive
        pygame.draw.circle(surface, color, (cx, y), r)


def draw_scroll_arc(
    surface: pygame.Surface,
    theme: Theme,
    current_offset: float,
    max_offset: float,
    visible_span: int,
) -> None:
    """Arc along the bezel edge showing scroll position within a list
    whose visible window spans `visible_span` px against `max_offset` px
    of overflow. No-op while nothing overflows (max_offset <= 0)."""
    if max_offset <= 0:
        return
    cx, cy = scaling.center_x(), scaling.center_y()
    r = scaling.visible_radius() - scaling.s(4)
    visible_frac = min(1.0, visible_span / (visible_span + max_offset))
    total_arc = math.radians(40)
    arc_len = max(math.radians(4), total_arc * visible_frac)
    progress = current_offset / max_offset
    start = math.radians(-20) + (total_arc - arc_len) * progress
    rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
    pygame.draw.arc(surface, theme.hint, rect, -(start + arc_len), -start, max(1, scaling.s(2)))

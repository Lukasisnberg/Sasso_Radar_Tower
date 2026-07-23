"""Shared drawing helpers for the round radar display."""

import math
from typing import Optional

import pygame

from flugradar.display import scaling
from flugradar.display.fonts import get_font
from flugradar.display.theme import Theme


def fit_text(text: str, font: pygame.font.Font, max_width: int) -> str:
    if max_width <= 0 or not text:
        return text
    if font.size(text)[0] <= max_width:
        return text
    for n in range(len(text), 0, -1):
        trial = text[:n] + "…"
        if font.size(trial)[0] <= max_width:
            return trial
    return "…"


def draw_center_text(
    surface: pygame.Surface,
    text: str,
    y: int,
    font: pygame.font.Font,
    color: tuple[int, int, int],
) -> int:
    h = font.get_height()
    max_w = scaling.circle_half_width_at_row(y, h) * 2
    line = fit_text(text, font, max_w)
    rendered = font.render(line, True, color)
    rect = rendered.get_rect(midtop=(scaling.center_x(), y))
    surface.blit(rendered, rect)
    return y + h + scaling.s(4)


def draw_dashed_circle(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    width: int = 2,
) -> None:
    if radius <= 0:
        return
    dash = max(1.0, float(scaling.s(7)))
    gap = max(1.0, float(scaling.s(15)))
    pattern = dash + gap
    cx, cy = center
    steps = max(360, int(math.ceil(2 * math.pi * radius / 2.0)))
    angle_step = (2 * math.pi) / steps
    arc_step = angle_step * radius
    run: list[tuple[int, int]] = []
    arc_pos = 0.0

    def flush():
        if len(run) >= 2:
            pygame.draw.lines(surface, color, False, run, width)
        run.clear()

    for i in range(steps + 1):
        angle = i * angle_step
        in_dash = (arc_pos % pattern) < dash
        pt = (int(cx + radius * math.cos(angle)),
              int(cy + radius * math.sin(angle)))
        if in_dash:
            run.append(pt)
        elif run:
            flush()
        arc_pos += arc_step
    flush()


_bezel_overlay: Optional[pygame.Surface] = None
_bezel_key: Optional[tuple] = None


def apply_round_bezel(surface: pygame.Surface, theme: Theme) -> None:
    global _bezel_overlay, _bezel_key
    size = surface.get_size()
    cx, cy = scaling.center_x(), scaling.center_y()
    vr = scaling.visible_radius()
    key = (size, cx, cy, vr, theme.background)
    if _bezel_overlay is None or _bezel_key != key:
        _bezel_overlay = pygame.Surface(size, pygame.SRCALPHA)
        _bezel_overlay.fill((*theme.background, 255))
        pygame.draw.circle(_bezel_overlay, (0, 0, 0, 0), (cx, cy), vr)
        _bezel_key = key
    surface.blit(_bezel_overlay, (0, 0))

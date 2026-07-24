"""Software screen dimming.

A physical backlight sysfs path can't be assumed for every panel/driver
combination, so "brightness" here means a translucent black overlay drawn
over the finished frame rather than an actual PWM/backlight write. This is
deliberately conservative: it works identically on every Pi + display
combination, at the cost of not being a true hardware dim.
"""

import datetime
from typing import Optional

import pygame


def _parse_hhmm(value: str) -> Optional[datetime.time]:
    try:
        h, m = value.split(":")
        return datetime.time(int(h), int(m))
    except (ValueError, AttributeError, TypeError):
        return None


def within_time_window(
    start: str, end: str, now: Optional[datetime.time] = None
) -> bool:
    """HH:MM strings. Handles windows that wrap past midnight (22:00-06:00)."""
    now = now if now is not None else datetime.datetime.now().time()
    start_t = _parse_hhmm(start)
    end_t = _parse_hhmm(end)
    if start_t is None or end_t is None:
        return False
    if start_t <= end_t:
        return start_t <= now < end_t
    return now >= start_t or now < end_t


def effective_brightness(settings, now: Optional[datetime.time] = None) -> int:
    """0-100. Applies the night-mode cap if it's currently within its window."""
    b = settings.brightness
    if settings.night_mode_enabled and within_time_window(
        settings.night_mode_start, settings.night_mode_end, now
    ):
        b = min(b, settings.night_mode_brightness)
    return max(0, min(100, b))


def apply_dim_overlay(surface: pygame.Surface, brightness: int) -> None:
    """Darken `surface` in place to represent `brightness` (0-100)."""
    brightness = max(0, min(100, brightness))
    if brightness >= 100:
        return
    alpha = int(255 * (100 - brightness) / 100)
    if alpha <= 0:
        return
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, alpha))
    surface.blit(overlay, (0, 0))

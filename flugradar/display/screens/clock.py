"""Clock + weather screen — shows time, date, and current conditions.

Centered layout fitted to the round display with Dieter Rams typography.
"""

import time
from typing import Optional

import pygame

from flugradar.display import nav, scaling
from flugradar.display.draw_helpers import draw_center_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import Theme


class ClockScreen:
    """Full-screen clock with optional weather overlay."""

    def __init__(self, screen_size: int, theme: Theme) -> None:
        self.size = screen_size
        self.theme = theme
        self.temperature: Optional[str] = None
        self.condition: Optional[str] = None
        self._fonts_ready = False
        self._font_time: Optional[pygame.font.Font] = None
        self._font_sec: Optional[pygame.font.Font] = None
        self._font_date: Optional[pygame.font.Font] = None
        self._font_weather: Optional[pygame.font.Font] = None
        self._font_hint: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._font_time = get_font(scaling.s(36), bold=True, mono=True)
            self._font_sec = get_font(scaling.s(14), mono=True)
            self._font_date = get_font(scaling.s(10))
            self._font_weather = get_font(scaling.s(12))
            self._font_hint = get_font(scaling.s(7))
            self._fonts_ready = True

    def set_weather(self, temperature: str, condition: str) -> None:
        self.temperature = temperature
        self.condition = condition

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)

        cx = scaling.center_x()
        cy = scaling.center_y()

        now = time.localtime()
        time_str = time.strftime("%H:%M", now)
        seconds_str = time.strftime(":%S", now)
        date_str = time.strftime("%A, %d %B %Y", now)

        time_surf = self._font_time.render(time_str, True, self.theme.label)
        sec_surf = self._font_sec.render(seconds_str, True, self.theme.muted)

        combined_w = time_surf.get_width() + sec_surf.get_width() + scaling.s(2)
        time_x = cx - combined_w // 2
        time_y = cy - scaling.s(50)

        surface.blit(time_surf, (time_x, time_y))
        surface.blit(sec_surf, (
            time_x + time_surf.get_width() + scaling.s(2),
            time_y + time_surf.get_height() - sec_surf.get_height() - scaling.s(2),
        ))

        y = time_y + time_surf.get_height() + scaling.s(8)
        y = draw_center_text(surface, date_str, y, self._font_date, self.theme.muted)

        if self.temperature:
            y += scaling.s(6)
            weather_str = self.temperature
            if self.condition:
                weather_str += f"  {self.condition}"
            y = draw_center_text(surface, weather_str, y, self._font_weather, self.theme.label)

        hint_y = cy + int(scaling.visible_radius() * 0.68)
        draw_center_text(surface, "swipe up for radar", hint_y, self._font_hint, self.theme.hint)

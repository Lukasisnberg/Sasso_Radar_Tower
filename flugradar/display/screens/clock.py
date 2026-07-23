"""Clock + weather screen — shows time, date, and current conditions."""

import time
from typing import Optional

import pygame

from flugradar.display.fonts import get_font
from flugradar.display.theme import Theme


class ClockScreen:
    """Full-screen clock with optional weather overlay."""

    def __init__(self, screen_size: int, theme: Theme) -> None:
        self.size = screen_size
        self.theme = theme
        self.temperature: Optional[str] = None
        self.condition: Optional[str] = None
        self._font_time: Optional[pygame.font.Font] = None
        self._font_date: Optional[pygame.font.Font] = None
        self._font_weather: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if self._font_time is None:
            self._font_time = get_font(72, bold=True, mono=True)
            self._font_date = get_font(20)
            self._font_weather = get_font(28)
            self._font_sm = get_font(13)

    def set_weather(self, temperature: str, condition: str) -> None:
        self.temperature = temperature
        self.condition = condition

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)
        cx = self.size // 2

        now = time.localtime()
        time_str = time.strftime("%H:%M", now)
        seconds_str = time.strftime(":%S", now)
        date_str = time.strftime("%A, %d %B %Y", now)

        time_surf = self._font_time.render(time_str, True, self.theme.compass_text)
        sec_surf = self._font_date.render(seconds_str, True, self.theme.range_label)

        time_x = cx - (time_surf.get_width() + sec_surf.get_width()) // 2
        time_y = self.size // 2 - 80
        surface.blit(time_surf, (time_x, time_y))
        surface.blit(sec_surf, (
            time_x + time_surf.get_width() + 2,
            time_y + time_surf.get_height() - sec_surf.get_height() - 4,
        ))

        date_surf = self._font_date.render(date_str, True, self.theme.range_label)
        surface.blit(date_surf, (cx - date_surf.get_width() // 2, time_y + 90))

        if self.temperature:
            weather_str = self.temperature
            if self.condition:
                weather_str += f"  {self.condition}"
            w_surf = self._font_weather.render(weather_str, True, self.theme.info_text)
            surface.blit(w_surf, (cx - w_surf.get_width() // 2, time_y + 140))

        hint = self._font_sm.render("swipe up for radar", True, self.theme.radar_ring)
        surface.blit(hint, (cx - hint.get_width() // 2, self.size - 40))

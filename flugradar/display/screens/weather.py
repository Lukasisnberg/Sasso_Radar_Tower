"""Weather forecast screen — next 3 days, from Tomorrow.io.

Reached by swiping right from the Clock screen (the screen that already
shows current conditions) -- mirrors the existing "swipe right to enter,
swipe left/down to return" pattern already used elsewhere for auxiliary
screens off the main navigation ring.
"""

import time
from typing import Optional

import pygame

from flugradar.data_sources.weather import DailyForecast
from flugradar.display import nav, scaling
from flugradar.display.draw_helpers import fit_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme
from flugradar.display.weather_icons import draw_weather_icon


class WeatherScreen:
    """3-day forecast, one column per day, with a hand-drawn condition icon."""

    def __init__(self, screen_size: int, theme: Theme, temperature_unit: str = "c") -> None:
        self.size = screen_size
        self.theme = theme
        self.temperature_unit = temperature_unit
        self.forecast: list[DailyForecast] = []
        self.has_key = False
        self._fonts_ready = False
        self._day_font: Optional[pygame.font.Font] = None
        self._temp_font: Optional[pygame.font.Font] = None
        self._cond_font: Optional[pygame.font.Font] = None
        self._msg_font: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._day_font = get_font(scaling.s(TOKENS.font_standard), bold=True)
            self._temp_font = get_font(scaling.s(TOKENS.font_value), mono=True)
            self._cond_font = get_font(scaling.s(TOKENS.font_small))
            self._msg_font = get_font(scaling.s(TOKENS.font_standard))
            self._fonts_ready = True

    def set_forecast(self, forecast: list[DailyForecast], has_key: bool) -> None:
        self.forecast = forecast
        self.has_key = has_key

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)
        nav.draw_breadcrumb(surface, ["Radar", "Weather"], self.theme)

        top = nav.content_top_y()
        bottom = nav.content_bottom_y()

        if not self.has_key:
            self._draw_message(surface, "No Tomorrow.io key configured", top, bottom)
        elif not self.forecast:
            self._draw_message(surface, "Forecast unavailable", top, bottom)
        else:
            self._draw_columns(surface, top, bottom)

        nav.draw_footer_buttons(surface, ["radar"], self.theme)

    def _draw_message(self, surface: pygame.Surface, text: str, top: int, bottom: int) -> None:
        y = (top + bottom) // 2 - self._msg_font.get_height() // 2
        self._blit_centered(surface, text, scaling.center_x(), y, self._msg_font,
                             self.theme.muted, self.size - scaling.s(40))

    def _draw_columns(self, surface: pygame.Surface, top: int, bottom: int) -> None:
        days = self.forecast[:3]
        col_count = len(days)
        col_w = self.size // max(1, col_count)
        max_text_w = col_w - scaling.s(10)

        icon_r = scaling.s(24)
        icon_y = top + scaling.s(16) + icon_r

        day_y = icon_y + icon_r + scaling.s(14)
        temp_y = day_y + self._day_font.get_height() + scaling.s(4)
        cond_y = temp_y + self._temp_font.get_height() + scaling.s(8)

        for i, day in enumerate(days):
            cx = col_w * i + col_w // 2
            draw_weather_icon(
                surface, day.weather_code, (cx, icon_y), icon_r,
                self.theme.muted, self.theme.sweep_colour,
            )
            self._blit_centered(surface, _day_label(day.date, i), cx, day_y,
                                 self._day_font, self.theme.label, max_text_w)
            self._blit_centered(surface, day.temp_range_str(self.temperature_unit), cx, temp_y,
                                 self._temp_font, self.theme.label, max_text_w)
            if cond_y + self._cond_font.get_height() <= bottom:
                self._blit_centered(surface, day.condition or "—", cx, cond_y,
                                     self._cond_font, self.theme.muted, max_text_w)

    @staticmethod
    def _blit_centered(surface, text, cx, y, font, color, max_w) -> None:
        line = fit_text(text, font, max_w)
        rendered = font.render(line, True, color)
        surface.blit(rendered, rendered.get_rect(midtop=(cx, y)))

    def handle_tap(self, x: int, y: int) -> str:
        idx = nav.tap_footer_button(x, y, 1)
        if idx is not None:
            return "radar"
        return ""


def _day_label(date_str: str, index: int) -> str:
    if index == 0:
        return "Today"
    try:
        return time.strftime("%a", time.strptime(date_str, "%Y-%m-%d"))
    except ValueError:
        return date_str or "—"

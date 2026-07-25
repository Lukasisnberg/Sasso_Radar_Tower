"""Weather screen — current conditions + 5-day forecast.

Layout follows docs/weather-screen-mockup.svg (see
docs/prompt-wetterscreen.md): header (location + weekday/time), current
weather (icon + hero temperature + condition text), three core values
(wind / feels-like / rain chance), a hairline divider, a five-day
forecast arced to follow the disc's curvature, and a screen indicator at
the bottom.

The SVG is a position/proportion reference only -- it is never rendered
or embedded, the screen is rebuilt in pygame like every other screen.
Where its hex colours disagree with theme.py's tokens, the tokens win
(the mockup shows intent, not binding values); UI text stays English to
match every other screen in the app, even though the mockup itself is
labelled in German.

Reached by swiping right from the Clock screen; mirrors the existing
"swipe right to enter, swipe left/down to return" pattern already used
for auxiliary screens off the main navigation ring.
"""

import time
from typing import Optional

import pygame

from flugradar.data_sources.weather import DailyForecast, WeatherData
from flugradar.display import nav, scaling
from flugradar.display.draw_helpers import render_tracked_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme
from flugradar.display.weather_icons import draw_weather_icon

# The hero temperature is the sole focal element of the current-weather
# block, so it intentionally exceeds the 4 UI font tiers -- same
# documented-multiple-of-font_title approach as the clock screen's hero
# time (flugradar/display/screens/clock.py, _HERO_TIME_SCALE).
_HERO_TEMP_SCALE = 4.0

_FORECAST_DAYS = 5

# Fractions of scaling.visible_radius() from screen centre, read off the
# mockup's disc (centre 360,360, r=352 on its 720px canvas) rather than
# copied as literal pixels, so the layout scales to any screen_size.
_LOCATION_Y_FRAC = -0.6875
_SUBHEAD_Y_FRAC = -0.6080
_ICON_DX_FRAC = -0.1761
_ICON_DY_FRAC = -0.4034
_ICON_R_FRAC = 0.0966
_TEMP_DX_FRAC = 0.0909
_TEMP_Y_FRAC = -0.2500
_CONDITION_Y_FRAC = -0.1080
_VALUES_LABEL_Y_FRAC = 0.0341
_VALUES_VALUE_Y_FRAC = 0.1136
_VALUES_DX_FRAC = 0.3693
_HAIRLINE_Y_FRAC = 0.2159
_HAIRLINE_HALFWIDTH_FRAC = 0.3125
# One entry per forecast column, outer-to-outer: the mockup's own y
# offsets bow the row to follow the disc's curvature rather than sitting
# dead flat.
_FORECAST_LABEL_Y_FRAC = (0.3125, 0.2614, 0.2443, 0.2614, 0.3125)
_FORECAST_DX_FRAC = (-0.5966, -0.2983, 0.0, 0.2983, 0.5966)
_FORECAST_ICON_R_FRAC = 0.0341
_FORECAST_ICON_Y_OFFSET_FRAC = 0.0966  # label baseline -> icon centre
_FORECAST_HI_Y_OFFSET_FRAC = 0.2216
_FORECAST_LO_Y_OFFSET_FRAC = 0.2841
_INDICATOR_LABEL_GAP = 10  # px (reference units) between dots and label

# Placeholder data for the layout skeleton -- Ausbaustufe "Wetterscreen",
# Schritt 1 (docs/prompt-wetterscreen.md): real Tomorrow.io wiring lands
# in Schritt 3. Numbers match the mockup's own example values.
_EXAMPLE_CURRENT = WeatherData(
    temperature_c=21.0,
    wind_speed_ms=12.0 / 3.6,
    weather_code=1100,
    condition="Mostly Clear",
)
_EXAMPLE_FEELS_LIKE_C = 20.0
_EXAMPLE_RAIN_CHANCE_PCT = 5.0
_EXAMPLE_FORECAST: list[DailyForecast] = [
    DailyForecast(date="2026-01-03", temp_min_c=13, temp_max_c=23, weather_code=1000, condition="Clear"),
    DailyForecast(date="2026-01-04", temp_min_c=14, temp_max_c=24, weather_code=1000, condition="Clear"),
    DailyForecast(date="2026-01-05", temp_min_c=11, temp_max_c=19, weather_code=1001, condition="Cloudy"),
    DailyForecast(date="2026-01-06", temp_min_c=10, temp_max_c=17, weather_code=1001, condition="Cloudy"),
    DailyForecast(date="2026-01-07", temp_min_c=12, temp_max_c=22, weather_code=1000, condition="Clear"),
]


class WeatherScreen:
    """Current conditions + 5-day forecast, laid out per the mockup."""

    def __init__(
        self,
        screen_size: int,
        theme: Theme,
        temperature_unit: str = "c",
        distance_unit: str = "km",
        time_format: str = "24h",
        location_label: str = "",
    ) -> None:
        self.size = screen_size
        self.theme = theme
        self.temperature_unit = temperature_unit
        self.distance_unit = distance_unit
        self.time_format = time_format
        self.location_label = location_label
        self._fonts_ready = False
        self._location_font: Optional[pygame.font.Font] = None
        self._subhead_font: Optional[pygame.font.Font] = None
        self._condition_font: Optional[pygame.font.Font] = None
        self._value_label_font: Optional[pygame.font.Font] = None
        self._value_font: Optional[pygame.font.Font] = None
        self._forecast_day_font: Optional[pygame.font.Font] = None
        self._forecast_hi_font: Optional[pygame.font.Font] = None
        self._forecast_lo_font: Optional[pygame.font.Font] = None
        self._indicator_font: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if self._fonts_ready:
            return
        self._location_font = get_font(scaling.s(TOKENS.font_title))
        self._subhead_font = get_font(scaling.s(TOKENS.font_standard))
        self._condition_font = get_font(scaling.s(TOKENS.font_title))
        self._value_label_font = get_font(scaling.s(TOKENS.font_standard))
        self._value_font = get_font(scaling.s(TOKENS.font_standard), mono=True)
        self._forecast_day_font = get_font(scaling.s(TOKENS.font_standard))
        self._forecast_hi_font = get_font(scaling.s(TOKENS.font_standard), mono=True)
        self._forecast_lo_font = get_font(scaling.s(TOKENS.font_small), mono=True)
        self._indicator_font = get_font(scaling.s(TOKENS.font_standard))
        self._fonts_ready = True

    def _y(self, frac: float) -> int:
        return scaling.center_y() + int(frac * scaling.visible_radius())

    def _x(self, frac: float) -> int:
        return scaling.center_x() + int(frac * scaling.visible_radius())

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)

        self._draw_header(surface)
        self._draw_current(surface)
        self._draw_values_row(surface)
        self._draw_hairline(surface)
        self._draw_forecast_row(surface)
        self._draw_screen_indicator(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        # location_label is always app-controlled (a preset name or a
        # short "lat, lon" fallback -- flugradar.config.locations
        # .location_display_name()), never arbitrary-length external
        # text, so it doesn't need fit_text's overflow protection the
        # way e.g. aircraft callsigns/registrations do elsewhere.
        cx = scaling.center_x()
        location = (self.location_label or "—").upper()
        loc_surf = render_tracked_text(self._location_font, location, self.theme.muted, spacing=scaling.s(3))
        surface.blit(loc_surf, loc_surf.get_rect(midtop=(cx, self._y(_LOCATION_Y_FRAC))))

        now = time.localtime()
        if self.time_format == "12h":
            clock_str = time.strftime("%I:%M", now).lstrip("0") or "0"
        else:
            clock_str = time.strftime("%H:%M", now)
        subhead = f"{time.strftime('%a', now)} · {clock_str}"
        sub_surf = self._subhead_font.render(subhead, True, self.theme.hint)
        surface.blit(sub_surf, sub_surf.get_rect(midtop=(cx, self._y(_SUBHEAD_Y_FRAC))))

    def _draw_current(self, surface: pygame.Surface) -> None:
        wx = _EXAMPLE_CURRENT
        icon_cx = self._x(_ICON_DX_FRAC)
        icon_cy = self._y(_ICON_DY_FRAC)
        icon_r = int(_ICON_R_FRAC * scaling.visible_radius())
        draw_weather_icon(surface, wx.weather_code, (icon_cx, icon_cy), icon_r,
                           self.theme.muted, self.theme.sweep_colour)

        temp_font = get_font(scaling.s(round(TOKENS.font_title * _HERO_TEMP_SCALE)), bold=True)
        temp_str = _bare_temp_str(wx.temperature_c, self.temperature_unit)
        temp_surf = temp_font.render(temp_str, True, self.theme.label)
        surface.blit(temp_surf, temp_surf.get_rect(midtop=(self._x(_TEMP_DX_FRAC), self._y(_TEMP_Y_FRAC))))

        cond_surf = self._condition_font.render(wx.condition or "—", True, self.theme.muted)
        surface.blit(cond_surf, cond_surf.get_rect(midtop=(scaling.center_x(), self._y(_CONDITION_Y_FRAC))))

    def _draw_values_row(self, surface: pygame.Surface) -> None:
        wx = _EXAMPLE_CURRENT
        columns = (
            ("WIND", wx.wind_speed_str(self.distance_unit)),
            ("FEELS LIKE", _bare_temp_str(_EXAMPLE_FEELS_LIKE_C, self.temperature_unit)),
            ("RAIN", f"{_EXAMPLE_RAIN_CHANCE_PCT:.0f} %"),
        )
        label_y = self._y(_VALUES_LABEL_Y_FRAC)
        value_y = self._y(_VALUES_VALUE_Y_FRAC)
        dxs = (-_VALUES_DX_FRAC, 0.0, _VALUES_DX_FRAC)
        for (label, value), dx in zip(columns, dxs):
            cx = self._x(dx)
            if not value:
                continue
            lbl_surf = render_tracked_text(self._value_label_font, label, self.theme.hint, spacing=scaling.s(1))
            surface.blit(lbl_surf, lbl_surf.get_rect(midtop=(cx, label_y)))
            val_surf = self._value_font.render(value, True, self.theme.label)
            surface.blit(val_surf, val_surf.get_rect(midtop=(cx, value_y)))

    def _draw_hairline(self, surface: pygame.Surface) -> None:
        y = self._y(_HAIRLINE_Y_FRAC)
        half_w = int(_HAIRLINE_HALFWIDTH_FRAC * scaling.visible_radius())
        cx = scaling.center_x()
        hairline = pygame.Surface((half_w * 2, 1), pygame.SRCALPHA)
        hairline.fill((*self.theme.radar_ring, TOKENS.hairline_alpha))
        surface.blit(hairline, (cx - half_w, y))

    def _draw_forecast_row(self, surface: pygame.Surface) -> None:
        days = _EXAMPLE_FORECAST[:_FORECAST_DAYS]
        icon_r = int(_FORECAST_ICON_R_FRAC * scaling.visible_radius())
        for i, day in enumerate(days):
            dx = _FORECAST_DX_FRAC[i]
            label_y_frac = _FORECAST_LABEL_Y_FRAC[i]
            cx = self._x(dx)
            label_y = self._y(label_y_frac)

            day_label = _weekday_label(day.date)
            day_surf = render_tracked_text(self._forecast_day_font, day_label, self.theme.muted, spacing=scaling.s(1))
            surface.blit(day_surf, day_surf.get_rect(midtop=(cx, label_y)))

            icon_cy = self._y(label_y_frac + _FORECAST_ICON_Y_OFFSET_FRAC)
            draw_weather_icon(surface, day.weather_code, (cx, icon_cy), icon_r,
                               self.theme.muted, self.theme.muted)

            hi_str = _bare_temp_str(day.temp_max_c, self.temperature_unit)
            hi_surf = self._forecast_hi_font.render(hi_str, True, self.theme.label)
            surface.blit(hi_surf, hi_surf.get_rect(midtop=(cx, self._y(label_y_frac + _FORECAST_HI_Y_OFFSET_FRAC))))

            lo_str = _bare_temp_str(day.temp_min_c, self.temperature_unit)
            lo_surf = self._forecast_lo_font.render(lo_str, True, self.theme.hint)
            surface.blit(lo_surf, lo_surf.get_rect(midtop=(cx, self._y(label_y_frac + _FORECAST_LO_Y_OFFSET_FRAC))))

    def _draw_screen_indicator(self, surface: pygame.Surface) -> None:
        rect = nav.footer_button_rects(1)[0]
        cx = rect.centerx
        dot_r = max(2, scaling.s(3))
        gap = scaling.s(18)
        dot_count = 4
        span = (dot_count - 1) * gap
        x0 = cx - span // 2
        dot_y = rect.top + rect.height // 3
        for i in range(dot_count):
            colour = self.theme.sweep_colour if i == 0 else self.theme.page_dot_inactive
            pygame.draw.circle(surface, colour, (x0 + i * gap, dot_y), dot_r)

        label_surf = render_tracked_text(self._indicator_font, "WEATHER", self.theme.hint, spacing=scaling.s(2))
        label_y = dot_y + scaling.s(_INDICATOR_LABEL_GAP)
        surface.blit(label_surf, label_surf.get_rect(midtop=(cx, label_y)))

    def handle_tap(self, x: int, y: int) -> str:
        idx = nav.tap_footer_button(x, y, 1)
        if idx is not None:
            return "radar"
        return ""


def _bare_temp_str(temp_c: float, unit: str) -> str:
    """Degree-only formatting (no unit letter) -- the mockup's minimalist
    style for the hero/feels-like/forecast temperatures. Distinct from
    WeatherData.temperature_str(), which is used elsewhere (e.g. the
    clock screen's status line) and does include the unit letter."""
    if unit == "f":
        return f"{temp_c * 9 / 5 + 32:.0f}°"
    return f"{temp_c:.0f}°"


def _weekday_label(date_str: str) -> str:
    try:
        return time.strftime("%a", time.strptime(date_str, "%Y-%m-%d")).upper()
    except ValueError:
        return "—"

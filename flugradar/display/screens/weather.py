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
(the mockup shows intent, not binding values); UI text is German to
match every other screen in the app and the mockup's own labelling.

Reached by swiping right from the Clock screen; mirrors the existing
"swipe right to enter, swipe left/down to return" pattern already used
for auxiliary screens off the main navigation ring.
"""

import time
from typing import Optional

import pygame

from flugradar.data_sources.route_progress import format_duration
from flugradar.data_sources.weather import DailyForecast, WeatherData
from flugradar.display import nav, scaling
from flugradar.display.de_dates import weekday_short
from flugradar.display.draw_helpers import render_tracked_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme
from flugradar.display.weather_icons import draw_weather_icon

# The hero temperature is the sole focal element of the current-weather
# block, so it intentionally exceeds the 4 UI font tiers -- same
# documented-multiple-of-font_title approach as the clock screen's hero
# time (flugradar/display/screens/clock.py, _HERO_TIME_SCALE). Smaller
# than the mockup's own proportions: fitting a hero number *and* a full
# 5-day forecast (weekday + icon + two temperatures each) into the
# available band below the header leaves no room for a bigger one.
_HERO_TEMP_SCALE = 2.9

_FORECAST_DAYS = 5

# Horizontal layout is read off the mockup's disc as fractions of
# scaling.visible_radius() (centre 360,360, r=352 on its 720px canvas) --
# safe, since side-by-side elements can't overlap from a font-metric
# mismatch the way stacked ones can.
#
# Vertical layout is NOT copied as fixed fractions: the mockup's SVG
# <text> y is a baseline, pygame positions from a box top, and the
# mockup's own font sizes don't match TOKENS -- translating its absolute
# y-values 1:1 caused real overlap (the hero temperature and the
# condition text, on real hardware). Each block below is instead
# positioned relative to the *measured* bottom of the block above it
# (the same pattern clock.py/detail.py already use), which is correct
# regardless of exact font metrics.
_LOCATION_Y_FRAC = -0.6875
_SUBHEAD_Y_FRAC = -0.6080
_ICON_DX_FRAC = -0.1761
_ICON_DY_FRAC = -0.4034
_ICON_R_FRAC = 0.0966
_TEMP_DX_FRAC = 0.0909
_TEMP_Y_FRAC = -0.3000
_VALUES_DX_FRAC = 0.3693
_HAIRLINE_HALFWIDTH_FRAC = 0.3125
_FORECAST_DX_FRAC = (-0.5966, -0.2983, 0.0, 0.2983, 0.5966)
_FORECAST_ICON_R_FRAC = 0.0230
# Slight per-column vertical offset (reference px) so the forecast row
# gently bows rather than sitting dead flat -- "leicht gebogene Reihe" --
# much subtler than the mockup's own offsets, which read as jagged once
# translated onto real font metrics instead of the mockup's placeholder
# circles/text.
_FORECAST_ARC_OFFSET = (5, 2, 0, 2, 5)

# Kept tight -- everything from the hero temperature down to the bottom
# of the forecast row has to fit above the footer/screen-indicator zone,
# which starts at a fixed fraction of the circle regardless of how much
# content is above it (see nav.footer_button_rects()).
_CONDITION_GAP = 0
_VALUES_ROW_GAP = 6
_VALUES_LABEL_VALUE_GAP = 0
_HAIRLINE_GAP = 6
_FORECAST_ROW_GAP = 6
_FORECAST_ICON_GAP = 0
_FORECAST_HI_GAP = 0
_FORECAST_LO_GAP = 0
_INDICATOR_LABEL_GAP = 10  # px (reference units) between dots and label


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
        # Data state -- fed by RadarApp from the shared WeatherClient
        # (flugradar/data_sources/weather.py); this screen adds no data
        # source of its own. Defaults to "no key" rather than "loading",
        # since that's the actual initial state before app.py's first
        # settings read.
        self.has_key: bool = False
        self.current: Optional[WeatherData] = None
        self.is_stale: bool = False
        self.age_s: Optional[float] = None
        self.forecast: list[DailyForecast] = []
        self._fonts_ready = False
        self._location_font: Optional[pygame.font.Font] = None
        self._subhead_font: Optional[pygame.font.Font] = None
        self._hero_temp_font: Optional[pygame.font.Font] = None
        self._condition_font: Optional[pygame.font.Font] = None
        self._value_label_font: Optional[pygame.font.Font] = None
        self._value_font: Optional[pygame.font.Font] = None
        self._forecast_day_font: Optional[pygame.font.Font] = None
        self._forecast_hi_font: Optional[pygame.font.Font] = None
        self._forecast_lo_font: Optional[pygame.font.Font] = None
        self._indicator_font: Optional[pygame.font.Font] = None
        self._message_font: Optional[pygame.font.Font] = None

    def set_data(
        self,
        has_key: bool,
        current: Optional[WeatherData],
        is_stale: bool = False,
        age_s: Optional[float] = None,
        forecast: Optional[list[DailyForecast]] = None,
    ) -> None:
        self.has_key = has_key
        self.current = current
        self.is_stale = is_stale
        self.age_s = age_s
        self.forecast = forecast or []

    def _ensure_fonts(self) -> None:
        if self._fonts_ready:
            return
        self._location_font = get_font(scaling.s(TOKENS.font_title))
        self._subhead_font = get_font(scaling.s(TOKENS.font_standard))
        # Tabular figures (Abschnitt 15: "Tabellarische Ziffern für alle
        # Temperaturen und Werte, damit bei Aktualisierung nichts
        # springt") -- same bold+mono combination as the clock screen's
        # hero time (_HERO_TIME_SCALE), cached here like every other font
        # instead of rebuilt inline on every draw() call.
        self._hero_temp_font = get_font(
            scaling.s(round(TOKENS.font_title * _HERO_TEMP_SCALE)), bold=True, mono=True,
        )
        self._condition_font = get_font(scaling.s(TOKENS.font_title))
        self._value_label_font = get_font(scaling.s(TOKENS.font_standard))
        self._value_font = get_font(scaling.s(TOKENS.font_standard), mono=True)
        self._forecast_day_font = get_font(scaling.s(TOKENS.font_standard))
        self._forecast_hi_font = get_font(scaling.s(TOKENS.font_standard), mono=True)
        self._forecast_lo_font = get_font(scaling.s(TOKENS.font_small), mono=True)
        self._indicator_font = get_font(scaling.s(TOKENS.font_standard))
        self._message_font = get_font(scaling.s(TOKENS.font_standard))
        self._fonts_ready = True

    def _y(self, frac: float) -> int:
        return scaling.center_y() + int(frac * scaling.visible_radius())

    def _x(self, frac: float) -> int:
        return scaling.center_x() + int(frac * scaling.visible_radius())

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)

        header_bottom = self._draw_header(surface)

        if not self.has_key:
            self._draw_message(surface, header_bottom, "Kein Tomorrow.io-Schlüssel konfiguriert", "Im Portal hinzufügen")
        elif self.current is None:
            self._draw_message(surface, header_bottom, "Wetter nicht verfügbar")
        else:
            y = self._draw_current(surface)
            y = self._draw_values_row(surface, y)
            y = self._draw_hairline(surface, y)
            self._draw_forecast_row(surface, y)

        self._draw_screen_indicator(surface)

    def _draw_header(self, surface: pygame.Surface) -> int:
        """Location + weekday/time. Returns the subhead's bottom y, used
        to position the no-key/no-data messages below it."""
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
        subhead = f"{weekday_short(now.tm_wday)} · {clock_str}"
        # A stale reading (fetch failed, showing the last known values)
        # gets a quiet age disclaimer folded into the same line, rather
        # than a whole extra row -- there's no vertical room to spare
        # (see the gap constants above) and this is meant to be
        # unobtrusive ("dezenter Hinweis") anyway.
        if self.has_key and self.current is not None and self.is_stale and self.age_s is not None:
            subhead += f" · vor {format_duration(self.age_s)} aktualisiert"
        sub_surf = self._subhead_font.render(subhead, True, self.theme.hint)
        sub_rect = sub_surf.get_rect(midtop=(cx, self._y(_SUBHEAD_Y_FRAC)))
        surface.blit(sub_surf, sub_rect)
        return sub_rect.bottom

    def _draw_message(self, surface: pygame.Surface, top_y: int, *lines: str) -> None:
        rect = nav.footer_button_rects(1)[0]
        available = rect.top - top_y
        line_h = self._message_font.get_height() + scaling.s(4)
        y = top_y + max(0, (available - line_h * len(lines)) // 2)
        for line in lines:
            surf = self._message_font.render(line, True, self.theme.muted)
            surface.blit(surf, surf.get_rect(midtop=(scaling.center_x(), y)))
            y += line_h

    def _draw_current(self, surface: pygame.Surface) -> int:
        """Icon + hero temperature + condition text. Returns the y just
        below the condition text, for the next block to build on."""
        wx = self.current
        icon_cx = self._x(_ICON_DX_FRAC)
        icon_cy = self._y(_ICON_DY_FRAC)
        icon_r = int(_ICON_R_FRAC * scaling.visible_radius())
        # Only the current icon gets the theme accent -- forecast icons
        # stay neutral (Abschnitt 15: "Nur die Theme-Akzentfarbe ...
        # das aktuelle Icon", no colour-coding by condition elsewhere).
        # Day/night is a wall-clock heuristic for now -- Tomorrow.io's
        # realtime response doesn't carry sunrise/sunset in the field set
        # this client requests.
        draw_weather_icon(surface, wx.weather_code, (icon_cx, icon_cy), icon_r,
                           self.theme.sweep_colour, is_night=_is_night_now())

        temp_str = _bare_temp_str(wx.temperature_c, self.temperature_unit)
        temp_surf = self._hero_temp_font.render(temp_str, True, self.theme.label)
        temp_rect = temp_surf.get_rect(midtop=(self._x(_TEMP_DX_FRAC), self._y(_TEMP_Y_FRAC)))
        surface.blit(temp_surf, temp_rect)

        # Positioned off temp_rect.bottom rather than its own fixed
        # fraction -- the hero font is far larger than anything else on
        # screen, so a fraction read off the mockup's baseline (not top)
        # drifted out of sync with this font's real metrics and
        # overlapped the condition text on real hardware.
        cond_y = temp_rect.bottom + scaling.s(_CONDITION_GAP)
        cond_surf = self._condition_font.render(wx.condition or "—", True, self.theme.muted)
        cond_rect = cond_surf.get_rect(midtop=(scaling.center_x(), cond_y))
        surface.blit(cond_surf, cond_rect)
        return cond_rect.bottom

    def _draw_values_row(self, surface: pygame.Surface, start_y: int) -> int:
        wx = self.current
        feels_like = _bare_temp_str(wx.temperature_apparent_c, self.temperature_unit) \
            if wx.temperature_apparent_c is not None else ""
        rain = f"{wx.precipitation_probability_pct:.0f} %" \
            if wx.precipitation_probability_pct is not None else ""
        columns = (
            ("WIND", wx.wind_speed_str(self.distance_unit)),
            ("GEFÜHLT WIE", feels_like),
            ("REGEN", rain),
        )
        label_y = start_y + scaling.s(_VALUES_ROW_GAP)
        label_h = self._value_label_font.get_height()
        value_y = label_y + label_h + scaling.s(_VALUES_LABEL_VALUE_GAP)
        value_h = self._value_font.get_height()
        dxs = (-_VALUES_DX_FRAC, 0.0, _VALUES_DX_FRAC)
        for (label, value), dx in zip(columns, dxs):
            cx = self._x(dx)
            if not value:
                continue
            lbl_surf = render_tracked_text(self._value_label_font, label, self.theme.hint, spacing=scaling.s(1))
            surface.blit(lbl_surf, lbl_surf.get_rect(midtop=(cx, label_y)))
            val_surf = self._value_font.render(value, True, self.theme.label)
            surface.blit(val_surf, val_surf.get_rect(midtop=(cx, value_y)))
        return value_y + value_h

    def _draw_hairline(self, surface: pygame.Surface, start_y: int) -> int:
        y = start_y + scaling.s(_HAIRLINE_GAP)
        half_w = int(_HAIRLINE_HALFWIDTH_FRAC * scaling.visible_radius())
        cx = scaling.center_x()
        hairline = pygame.Surface((half_w * 2, 1), pygame.SRCALPHA)
        hairline.fill((*self.theme.radar_ring, TOKENS.hairline_alpha))
        surface.blit(hairline, (cx - half_w, y))
        return y + 1

    def _draw_forecast_row(self, surface: pygame.Surface, start_y: int) -> int:
        days = self.forecast[:_FORECAST_DAYS]
        icon_r = int(_FORECAST_ICON_R_FRAC * scaling.visible_radius())
        base_y = start_y + scaling.s(_FORECAST_ROW_GAP)
        day_h = self._forecast_day_font.get_height()
        hi_h = self._forecast_hi_font.get_height()
        bottom = base_y
        for i, day in enumerate(days):
            dx = _FORECAST_DX_FRAC[i]
            cx = self._x(dx)
            label_y = base_y + scaling.s(_FORECAST_ARC_OFFSET[i])

            day_label = _weekday_label(day.date)
            day_surf = render_tracked_text(self._forecast_day_font, day_label, self.theme.muted, spacing=scaling.s(1))
            surface.blit(day_surf, day_surf.get_rect(midtop=(cx, label_y)))

            icon_cy = label_y + day_h + scaling.s(_FORECAST_ICON_GAP) + icon_r
            # Always the day variant -- a forecast day has no single
            # "time of day" the way "right now" does.
            draw_weather_icon(surface, day.weather_code, (cx, icon_cy), icon_r, self.theme.muted)

            hi_y = icon_cy + icon_r + scaling.s(_FORECAST_HI_GAP)
            hi_str = _bare_temp_str(day.temp_max_c, self.temperature_unit)
            hi_surf = self._forecast_hi_font.render(hi_str, True, self.theme.label)
            surface.blit(hi_surf, hi_surf.get_rect(midtop=(cx, hi_y)))

            lo_y = hi_y + hi_h + scaling.s(_FORECAST_LO_GAP)
            lo_str = _bare_temp_str(day.temp_min_c, self.temperature_unit)
            lo_surf = self._forecast_lo_font.render(lo_str, True, self.theme.hint)
            lo_rect = lo_surf.get_rect(midtop=(cx, lo_y))
            surface.blit(lo_surf, lo_rect)
            bottom = max(bottom, lo_rect.bottom)
        return bottom

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

        label_surf = render_tracked_text(self._indicator_font, "WETTER", self.theme.hint, spacing=scaling.s(2))
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
        parsed = time.strptime(date_str, "%Y-%m-%d")
        return weekday_short(parsed.tm_wday).upper()
    except ValueError:
        return "—"


def _is_night_now() -> bool:
    """Rough wall-clock day/night heuristic for the current-conditions
    icon, not an astronomical sunrise/sunset calculation -- out of scope
    for this pass, and not requested by the brief (which only asks the
    icon *set* to offer day/night variants, not real astronomy)."""
    hour = time.localtime().tm_hour
    return hour < 6 or hour >= 20

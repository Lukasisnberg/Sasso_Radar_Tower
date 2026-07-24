"""Low-level radar drawing primitives: sweep, rings, compass, aircraft.

Enhanced with multi-line colored tags, aircraft silhouettes,
and alert rim flashing for military/emergency traffic.
"""

import math
import time
from typing import Optional

import pygame

from flugradar.data_sources.geo import km_to_unit, unit_label
from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.projection import ScreenProjection
from flugradar.display import scaling
from flugradar.display.aircraft_icons import (
    altitude_tag_color,
    draw_plane_icon,
    format_altitude,
)
from flugradar.display.fonts import get_font
from flugradar.display.theme import Theme

_TWO_PI = 2 * math.pi
_STROKE = 2


class RadarRenderer:
    """Draws the radar overlay onto a surface."""

    def __init__(
        self,
        screen_size: int,
        projection: ScreenProjection,
        theme: Theme,
        sweep_rpm: float = 6.0,
        ring_count: int = 4,
        distance_unit: str = "km",
    ) -> None:
        self.size = screen_size
        self.proj = projection
        self.theme = theme
        self.sweep_rpm = sweep_rpm
        self.ring_count = ring_count
        self.distance_unit = distance_unit
        self._sweep_surface = pygame.Surface((screen_size, screen_size), pygame.SRCALPHA)
        self._font_sm: Optional[pygame.font.Font] = None
        self._font_md: Optional[pygame.font.Font] = None
        self._font_lg: Optional[pygame.font.Font] = None
        self._font_num: Optional[pygame.font.Font] = None
        self._font_tag: Optional[pygame.font.Font] = None
        self._font_tag_sub: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if self._font_sm is None:
            self._font_sm = get_font(scaling.s(7))
            self._font_md = get_font(scaling.s(8))
            self._font_lg = get_font(scaling.s(10), bold=True)
            self._font_num = get_font(scaling.s(7), mono=True)
            self._font_tag = get_font(scaling.s(7))
            self._font_tag_sub = get_font(scaling.s(6))

    def sweep_angle(self) -> float:
        return (time.time() * self.sweep_rpm / 60.0 * _TWO_PI) % _TWO_PI

    def draw_background(self, surface: pygame.Surface) -> None:
        surface.fill(self.theme.background)

    def draw_rings(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        cx, cy = int(self.proj.centre[0]), int(self.proj.centre[1])
        for i in range(1, self.ring_count + 1):
            frac = i / self.ring_count
            radius_px = int(frac * self.size / 2)
            radius_km = frac * self.proj.radius_km
            pygame.draw.circle(
                surface, self.theme.radar_ring, (cx, cy), radius_px, 1
            )
            dist_val = km_to_unit(radius_km, self.distance_unit)
            label = f"{dist_val:.0f}{unit_label(self.distance_unit)}"
            txt = self._font_num.render(label, True, self.theme.range_label)
            surface.blit(txt, (cx + radius_px - txt.get_width() - 4, cy + 2))

    def draw_compass(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        cx, cy = int(self.proj.centre[0]), int(self.proj.centre[1])
        edge = self.size // 2 - 2
        cardinals = {0: "N", 90: "E", 180: "S", 270: "W"}
        for deg in range(0, 360, 10):
            angle_rad = math.radians(deg - 90)
            is_cardinal = deg in cardinals
            is_major = deg % 30 == 0
            if is_cardinal:
                tick_len = 15
            elif is_major:
                tick_len = 10
            else:
                tick_len = 5
            x_outer = cx + edge * math.cos(angle_rad)
            y_outer = cy + edge * math.sin(angle_rad)
            x_inner = cx + (edge - tick_len) * math.cos(angle_rad)
            y_inner = cy + (edge - tick_len) * math.sin(angle_rad)
            pygame.draw.line(
                surface, self.theme.compass_tick,
                (int(x_inner), int(y_inner)),
                (int(x_outer), int(y_outer)),
                _STROKE,
            )
            if is_cardinal:
                lbl = self._font_lg.render(cardinals[deg], True, self.theme.compass_text)
                lx = cx + (edge - 28) * math.cos(angle_rad) - lbl.get_width() / 2
                ly = cy + (edge - 28) * math.sin(angle_rad) - lbl.get_height() / 2
                surface.blit(lbl, (int(lx), int(ly)))

    def draw_centre(self, surface: pygame.Surface) -> None:
        cx, cy = int(self.proj.centre[0]), int(self.proj.centre[1])
        pygame.draw.circle(surface, self.theme.centre_dot, (cx, cy), 3)
        arm = 8
        pygame.draw.line(surface, self.theme.centre_dot, (cx - arm, cy), (cx + arm, cy), 1)
        pygame.draw.line(surface, self.theme.centre_dot, (cx, cy - arm), (cx, cy + arm), 1)

    def draw_sweep(self, surface: pygame.Surface) -> None:
        self._sweep_surface.fill((0, 0, 0, 0))
        cx, cy = self.proj.centre
        angle = self.sweep_angle()
        trail_arc = math.radians(30)
        steps = 40
        radius = self.size // 2
        for i in range(steps):
            frac = i / steps
            a = angle - frac * trail_arc
            alpha = int(self.theme.sweep_alpha_max * (1.0 - frac))
            colour = (*self.theme.sweep_colour, alpha)
            x = cx + radius * math.cos(a - math.pi / 2)
            y = cy + radius * math.sin(a - math.pi / 2)
            pygame.draw.line(
                self._sweep_surface, colour,
                (int(cx), int(cy)), (int(x), int(y)), _STROKE
            )
        surface.blit(self._sweep_surface, (0, 0))

    def _flight_icon_color(self, ac: Aircraft, is_selected: bool) -> tuple[int, int, int]:
        if ac.is_emergency:
            t = (time.time() * 4) % 2
            return self.theme.alert_flash_other if t < 1 else self.theme.alert_other
        if ac.is_military:
            t = (time.time() * 3) % 2
            return self.theme.alert_flash if t < 1 else self.theme.alert_military
        if is_selected:
            return self.theme.aircraft_selected
        return self.theme.aircraft_dot

    def _draw_aircraft_tag(
        self,
        surface: pygame.Surface,
        ac: Aircraft,
        ix: int, iy: int,
    ) -> pygame.Rect:
        tag_x = ix + scaling.s(12)
        tag_y = iy - scaling.s(8)

        cs_surf = self._font_tag.render(ac.display_label, True, self.theme.tag_callsign)
        surface.blit(cs_surf, (tag_x, tag_y))
        line_h = cs_surf.get_height() + 1
        tag_w = cs_surf.get_width()

        if ac.aircraft_type:
            type_surf = self._font_tag_sub.render(
                ac.aircraft_type, True, self.theme.tag_type
            )
            surface.blit(type_surf, (tag_x, tag_y + line_h))
            tag_w = max(tag_w, type_surf.get_width())

        alt_str = format_altitude(ac.altitude_ft)
        if alt_str:
            alt_color = altitude_tag_color(ac.vertical_rate_fpm, self.theme)
            alt_surf = self._font_tag_sub.render(alt_str, True, alt_color)
            surface.blit(alt_surf, (tag_x, tag_y + line_h * 2))
            tag_w = max(tag_w, alt_surf.get_width())

        return pygame.Rect(
            ix - scaling.s(14), iy - scaling.s(14),
            scaling.s(14) + tag_x - ix + tag_w + scaling.s(4),
            scaling.s(28) + line_h * 2,
        )

    def _draw_alert_rim(self, surface: pygame.Surface, ac: Aircraft) -> None:
        t = (time.time() * 4) % 1.0
        alpha = int(40 * abs(math.sin(t * math.pi)))
        if alpha < 5:
            return
        color = self.theme.alert_flash_other if ac.is_emergency else self.theme.alert_flash
        cx, cy = int(self.proj.centre[0]), int(self.proj.centre[1])
        rim_surf = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.circle(rim_surf, (*color, alpha), (cx, cy), self.size // 2, scaling.s(4))
        surface.blit(rim_surf, (0, 0))

    def draw_aircraft(
        self,
        surface: pygame.Surface,
        aircraft: list[Aircraft],
        selected_hex: Optional[str] = None,
    ) -> list[tuple[pygame.Rect, Aircraft]]:
        self._ensure_fonts()
        hit_rects: list[tuple[pygame.Rect, Aircraft]] = []
        alert_ac = None

        for ac in aircraft:
            if ac.lat is None or ac.lon is None:
                continue
            x, y = self.proj.geo_to_screen(ac.lat, ac.lon)
            if not self.proj.is_on_screen(x, y):
                continue
            ix, iy = int(x), int(y)
            is_sel = ac.icao_hex == selected_hex
            colour = self._flight_icon_color(ac, is_sel)

            heading = ac.track_deg if ac.track_deg is not None else 0.0
            draw_plane_icon(
                surface, ix, iy, heading, colour,
                aircraft_type=ac.aircraft_type or "",
                category=ac.category,
            )

            hit = self._draw_aircraft_tag(surface, ac, ix, iy)
            hit_rects.append((hit, ac))

            if ac.is_emergency or ac.is_military:
                alert_ac = ac

        if alert_ac:
            self._draw_alert_rim(surface, alert_ac)

        return hit_rects

    def draw_status_bar(
        self,
        surface: pygame.Surface,
        count: int,
        radius_km: float,
        weather_str: str = "",
    ) -> None:
        self._ensure_fonts()
        dist_val = km_to_unit(radius_km, self.distance_unit)
        ulbl = unit_label(self.distance_unit)
        parts = [f"{count} aircraft", f"{dist_val:.0f}{ulbl} range"]
        if weather_str:
            parts.append(weather_str)
        parts.append("adsb.fi")
        txt = self._font_sm.render(
            f"  {' | '.join(parts)}  ",
            True, self.theme.status_bar,
        )
        surface.blit(txt, (4, self.size - txt.get_height() - 4))

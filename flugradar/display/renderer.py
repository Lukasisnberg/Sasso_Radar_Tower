"""Low-level radar drawing primitives: sweep, rings, compass, aircraft."""

import math
import time
from typing import Optional

import pygame

from flugradar.data_sources.geo import km_to_unit, unit_label
from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.projection import ScreenProjection
from flugradar.display.theme import Theme

_TWO_PI = 2 * math.pi


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

    def _ensure_fonts(self) -> None:
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("monospace", 12)
            self._font_md = pygame.font.SysFont("monospace", 14)
            self._font_lg = pygame.font.SysFont("monospace", 18)

    def sweep_angle(self) -> float:
        """Current sweep angle in radians based on wall clock."""
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
            txt = self._font_sm.render(label, True, self.theme.range_label)
            surface.blit(txt, (cx + radius_px - txt.get_width() - 4, cy + 2))

    def draw_compass(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        cx, cy = int(self.proj.centre[0]), int(self.proj.centre[1])
        edge = self.size // 2 - 2
        cardinals = {0: "N", 90: "E", 180: "S", 270: "W"}
        for deg in range(0, 360, 10):
            angle_rad = math.radians(deg - 90)  # 0° = north = top
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
                2 if is_major else 1,
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
                (int(cx), int(cy)), (int(x), int(y)), 2
            )
        surface.blit(self._sweep_surface, (0, 0))

    def draw_aircraft(
        self,
        surface: pygame.Surface,
        aircraft: list[Aircraft],
        selected_hex: Optional[str] = None,
    ) -> list[tuple[pygame.Rect, Aircraft]]:
        """Draw aircraft dots and labels. Returns hit-rects for click detection."""
        self._ensure_fonts()
        hit_rects: list[tuple[pygame.Rect, Aircraft]] = []
        for ac in aircraft:
            if ac.lat is None or ac.lon is None:
                continue
            x, y = self.proj.geo_to_screen(ac.lat, ac.lon)
            if not self.proj.is_on_screen(x, y):
                continue
            ix, iy = int(x), int(y)
            is_sel = ac.icao_hex == selected_hex
            if ac.is_emergency:
                colour = self.theme.emergency
                dot_r = 6
            elif is_sel:
                colour = self.theme.aircraft_selected
                dot_r = 5
            else:
                colour = self.theme.aircraft_dot
                dot_r = 4

            pygame.draw.circle(surface, colour, (ix, iy), dot_r)

            if ac.track_deg is not None:
                hdg_rad = math.radians(ac.track_deg - 90)
                hx = ix + int(18 * math.cos(hdg_rad))
                hy = iy + int(18 * math.sin(hdg_rad))
                pygame.draw.line(surface, self.theme.heading_line, (ix, iy), (hx, hy), 1)

            label = ac.display_label
            alt_str = ""
            if ac.altitude_ft:
                fl = ac.altitude_ft // 100
                alt_str = f" FL{fl:03d}" if ac.altitude_ft >= 18000 else f" {ac.altitude_ft}ft"
            txt = self._font_sm.render(f"{label}{alt_str}", True, colour)
            tx = ix + dot_r + 4
            ty = iy - txt.get_height() // 2
            surface.blit(txt, (tx, ty))

            hit = pygame.Rect(ix - 16, iy - 16, 32, 32)
            hit_rects.append((hit, ac))

        return hit_rects

    def draw_status_bar(
        self,
        surface: pygame.Surface,
        count: int,
        radius_km: float,
    ) -> None:
        self._ensure_fonts()
        dist_val = km_to_unit(radius_km, self.distance_unit)
        ulbl = unit_label(self.distance_unit)
        txt = self._font_sm.render(
            f"  {count} aircraft | {dist_val:.0f}{ulbl} range  ",
            True, self.theme.status_bar,
        )
        surface.blit(txt, (4, self.size - txt.get_height() - 4))

"""Tracked-flight screen (Ausbaustufe 2, Schritt 5 -- docs/prompt-ausbaustufe-2.md).

Shows progress along a route for one specific, user-selected flight,
independent of whether it's currently on screen on the radar. Handles the
four edge cases from 5.3 explicitly rather than assuming the happy path:
no flight selected, no route known, aircraft out of reception range, and
(handled one level up, in RadarApp) landed/gone for good.
"""

from typing import Optional

import pygame

from flugradar.data_sources.aircraft_photo import get_photo_info, load_photo_surface
from flugradar.data_sources.airline_branding import display_flight_id, marketing_brand_name
from flugradar.data_sources.airports import format_route_endpoint
from flugradar.data_sources.geo import km_to_unit, unit_label
from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.route_progress import (
    format_duration,
    remaining_distance_km,
    remaining_time_s,
    route_progress_fraction,
    vertical_rate_label,
)
from flugradar.display import nav, scaling
from flugradar.display.aircraft_icons import altitude_tag_color, draw_plane_icon, format_altitude
from flugradar.display.draw_helpers import draw_center_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme


class TrackedFlightScreen:
    """Renders the one currently-tracked flight, if any."""

    def __init__(
        self, screen_size: int, theme: Theme,
        distance_unit: str = "km", aircraft_icon_set: str = "detailed",
    ) -> None:
        self.size = screen_size
        self.theme = theme
        self.distance_unit = distance_unit
        self.aircraft_icon_set = aircraft_icon_set
        self.aircraft: Optional[Aircraft] = None
        self.is_current: bool = False
        self.last_seen_ago_s: Optional[float] = None
        # See DetailScreen._get_photo -- avoids re-decoding/rescaling the
        # same JPEG every frame while this screen is showing.
        self._photo_cache: Optional[tuple[str, pygame.Surface]] = None
        self._fonts_ready = False
        self._font_title: Optional[pygame.font.Font] = None
        self._font_body: Optional[pygame.font.Font] = None
        self._font_detail: Optional[pygame.font.Font] = None
        self._font_num: Optional[pygame.font.Font] = None
        self._font_code: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._font_title = get_font(scaling.s(TOKENS.font_title), bold=True)
            self._font_body = get_font(scaling.s(TOKENS.font_standard))
            self._font_detail = get_font(scaling.s(TOKENS.font_small))
            self._font_num = get_font(scaling.s(TOKENS.font_small), mono=True)
            self._font_code = get_font(scaling.s(TOKENS.font_value), bold=True, mono=True)
            self._fonts_ready = True

    def set_tracking(
        self,
        aircraft: Optional[Aircraft],
        is_current: bool,
        last_seen_ago_s: Optional[float],
    ) -> None:
        self.aircraft = aircraft
        self.is_current = is_current
        self.last_seen_ago_s = last_seen_ago_s

    def _has_route(self, ac: Aircraft) -> bool:
        return None not in (ac.origin_lat, ac.origin_lon, ac.destination_lat, ac.destination_lon)

    def _footer_buttons_state(self) -> list[str]:
        return ["stop", "radar"] if self.aircraft is not None else ["radar"]

    def _get_photo(self, path: str, max_h: int, max_w: int, radius: int) -> Optional[pygame.Surface]:
        if self._photo_cache is not None and self._photo_cache[0] == path:
            return self._photo_cache[1]
        photo = load_photo_surface(path, max_h, max_w=max_w, radius=radius)
        if photo is not None:
            self._photo_cache = (path, photo)
        return photo

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)
        nav.draw_breadcrumb(surface, ["Radar", "Tracking"], self.theme)

        top = nav.content_top_y()
        bottom = nav.content_bottom_y()
        cx = scaling.center_x()
        y = top

        if self.aircraft is None:
            y = draw_center_text(surface, "No flight tracked", y, self._font_title, self.theme.label)
            y += scaling.s(6)
            for line in (
                "Select a flight on the radar, open its",
                "detail view, and tap \"Track\" in the footer.",
            ):
                y = draw_center_text(surface, line, y, self._font_body, self.theme.muted)
            nav.draw_footer_buttons(surface, self._footer_buttons_state(), self.theme)
            return

        ac = self.aircraft

        photo_info = get_photo_info(ac.icao_hex)
        if photo_info:
            max_h = scaling.s(42)
            max_w = int(scaling.visible_radius() * 1.3)
            photo = self._get_photo(photo_info["path"], max_h, max_w, scaling.s(6))
            if photo:
                rect = photo.get_rect(midtop=(cx, y))
                surface.blit(photo, rect)
                y += rect.height + scaling.s(4)

        flight_id = display_flight_id(flight_number=ac.flight_number or "", callsign=ac.callsign or "")
        y = draw_center_text(surface, flight_id, y, self._font_title, self.theme.label)

        brand = marketing_brand_name(ac.flight_number or ac.callsign or "")
        airline_name = ac.airline or brand or ""
        if airline_name:
            y = draw_center_text(surface, airline_name, y, self._font_detail, self.theme.muted)

        if not self.is_current:
            age = "just now" if (self.last_seen_ago_s or 0) < 60 else f"{format_duration(self.last_seen_ago_s)} ago"
            y += scaling.s(2)
            y = draw_center_text(
                surface, f"No current data · last seen {age}", y, self._font_detail, self.theme.emergency,
            )

        y += scaling.s(8)

        has_route = self._has_route(ac)
        if has_route:
            y = self._draw_progress_bar(surface, ac, y)
            y += scaling.s(10)
        elif ac.origin or ac.destination:
            label = format_route_endpoint(ac.origin) if ac.origin else "?"
            label += "  →  "
            label += format_route_endpoint(ac.destination) if ac.destination else "?"
            y = draw_center_text(surface, label, y, self._font_body, self.theme.route)
            y = draw_center_text(surface, "Route position unknown", y, self._font_detail, self.theme.hint)
            y += scaling.s(6)
        else:
            y = draw_center_text(surface, "Route unknown", y, self._font_detail, self.theme.hint)
            y += scaling.s(6)

        rows = self._telemetry_rows(ac)
        for text, font, color in rows:
            if y + font.get_height() > bottom:
                break
            y = draw_center_text(surface, text, y, font, color)

        nav.draw_footer_buttons(surface, self._footer_buttons_state(), self.theme)

    def _draw_progress_bar(self, surface: pygame.Surface, ac: Aircraft, y: int) -> int:
        cx = scaling.center_x()
        bar_y = y + scaling.s(20)
        half_w = min(scaling.circle_half_width_at_row(bar_y, scaling.s(4)), scaling.s(110))
        x0, x1 = cx - half_w, cx + half_w

        origin_lat, origin_lon = ac.origin_lat, ac.origin_lon
        dest_lat, dest_lon = ac.destination_lat, ac.destination_lon
        cur_lat = ac.lat if ac.lat is not None else origin_lat
        cur_lon = ac.lon if ac.lon is not None else origin_lon
        frac = route_progress_fraction(origin_lat, origin_lon, dest_lat, dest_lon, cur_lat, cur_lon)

        track_h = max(2, scaling.s(2))
        pygame.draw.line(surface, self.theme.radar_ring, (x0, bar_y), (x1, bar_y), track_h)
        fill_x = x0 + int((x1 - x0) * frac)
        pygame.draw.line(surface, self.theme.sweep_colour, (x0, bar_y), (fill_x, bar_y), track_h)

        draw_plane_icon(
            surface, fill_x, bar_y, 90.0, self.theme.sweep_colour,
            aircraft_type=ac.aircraft_type or "", category=ac.category, compact=True,
            icon_set=self.aircraft_icon_set,
        )

        origin_code = self._font_code.render((ac.origin or "?").upper(), True, self.theme.label)
        dest_code = self._font_code.render((ac.destination or "?").upper(), True, self.theme.label)
        surface.blit(origin_code, (x0, bar_y - scaling.s(10) - origin_code.get_height()))
        surface.blit(dest_code, (x1 - dest_code.get_width(), bar_y - scaling.s(10) - dest_code.get_height()))

        origin_city = self._font_detail.render(_city_only(ac.origin), True, self.theme.muted)
        dest_city = self._font_detail.render(_city_only(ac.destination), True, self.theme.muted)
        surface.blit(origin_city, (x0, bar_y + scaling.s(8)))
        surface.blit(dest_city, (x1 - dest_city.get_width(), bar_y + scaling.s(8)))

        row_y = bar_y + scaling.s(8) + origin_city.get_height() + scaling.s(6)
        remaining_km = remaining_distance_km(cur_lat, cur_lon, dest_lat, dest_lon)
        eta_s = remaining_time_s(remaining_km, ac.ground_speed_kt)
        dist_val = km_to_unit(remaining_km, self.distance_unit)
        summary = f"{dist_val:.0f} {unit_label(self.distance_unit)} remaining · ETA {format_duration(eta_s)}"
        row_y = draw_center_text(surface, summary, row_y, self._font_num, self.theme.info_text)
        return row_y

    def _telemetry_rows(self, ac: Aircraft) -> list[tuple[str, pygame.font.Font, tuple[int, int, int]]]:
        rows: list[tuple[str, pygame.font.Font, tuple[int, int, int]]] = []

        parts = []
        alt_str = format_altitude(ac.altitude_ft)
        if alt_str:
            parts.append(alt_str)
        if ac.ground_speed_kt is not None:
            parts.append(f"{ac.ground_speed_kt:.0f} kt")
        vs_label = vertical_rate_label(ac.vertical_rate_fpm)
        if vs_label and vs_label != "level":
            parts.append(vs_label)
        if parts:
            colour = altitude_tag_color(ac.vertical_rate_fpm, self.theme)
            rows.append((" · ".join(parts), self._font_num, colour))

        if ac.aircraft_type:
            rows.append((ac.aircraft_type, self._font_detail, self.theme.tag_type))

        if ac.registered_owner:
            rows.append((ac.registered_owner, self._font_detail, self.theme.muted))

        return rows

    def handle_tap(self, x: int, y: int) -> str:
        """Returns 'stop' (end tracking + go to radar), 'radar' (just go
        back, tracking continues), or '' for no action."""
        buttons = self._footer_buttons_state()
        idx = nav.tap_footer_button(x, y, len(buttons))
        if idx is not None:
            return buttons[idx]
        breadcrumb_y = scaling.center_y() - int(scaling.visible_radius() * 0.75)
        if y < breadcrumb_y + scaling.s(30):
            return "radar"
        return ""


def _city_only(code: Optional[str]) -> str:
    """format_route_endpoint() gives 'City (CODE)' or bare 'CODE' -- strip
    the code parenthetical for the small caption under the progress bar,
    where the code is already shown large above it."""
    if not code:
        return ""
    full = format_route_endpoint(code)
    if "(" in full:
        return full.split("(")[0].strip()
    return ""

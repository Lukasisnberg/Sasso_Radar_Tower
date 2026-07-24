"""Flight detail screen — photo header, airline info, telemetry, navigation."""

from typing import Optional

import pygame

from flugradar.data_sources.aircraft_photo import get_photo_info, load_photo_surface
from flugradar.data_sources.airline_branding import display_flight_id, marketing_brand_name
from flugradar.data_sources.airports import format_route_endpoint
from flugradar.data_sources.geo import km_to_unit, unit_label
from flugradar.data_sources.models import Aircraft
from flugradar.display import nav, scaling
from flugradar.display.aircraft_icons import format_altitude, altitude_tag_color
from flugradar.display.draw_helpers import draw_center_text, fit_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import Theme

_FOOTER_BUTTONS = ["prev", "next", "radar"]
_FOOTER_SINGLE = ["radar"]


class DetailScreen:
    """Renders detailed flight information with photo header and nav chrome."""

    def __init__(self, screen_size: int, theme: Theme, distance_unit: str = "km") -> None:
        self.size = screen_size
        self.theme = theme
        self.distance_unit = distance_unit
        self.aircraft: Optional[Aircraft] = None
        self._aircraft_list: list[Aircraft] = []
        self._selected_index: int = 0
        self._scroll = nav.ScrollState()
        self._fonts_ready = False
        self._title_font: Optional[pygame.font.Font] = None
        self._body_font: Optional[pygame.font.Font] = None
        self._detail_font: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._title_font = get_font(scaling.s(12), bold=True)
            self._body_font = get_font(scaling.s(9))
            self._detail_font = get_font(scaling.s(8))
            self._fonts_ready = True

    def set_aircraft(self, ac: Aircraft) -> None:
        self.aircraft = ac
        self._scroll.reset()

    def set_aircraft_list(self, aircraft: list[Aircraft]) -> None:
        self._aircraft_list = aircraft

    def _current_aircraft(self) -> Optional[Aircraft]:
        if self.aircraft is None:
            return None
        for ac in self._aircraft_list:
            if ac.icao_hex == self.aircraft.icao_hex:
                return ac
        return self.aircraft

    def _find_index(self) -> int:
        if self.aircraft is None:
            return 0
        for i, ac in enumerate(self._aircraft_list):
            if ac.icao_hex == self.aircraft.icao_hex:
                return i
        return 0

    def _navigate(self, delta: int) -> None:
        if not self._aircraft_list:
            return
        idx = self._find_index()
        idx = (idx + delta) % len(self._aircraft_list)
        self.aircraft = self._aircraft_list[idx]
        self._scroll.reset()

    def _build_rows(self, ac: Aircraft) -> list[tuple[str, pygame.font.Font, tuple[int, int, int]]]:
        rows = []

        flight_id = display_flight_id(
            flight_number=ac.flight_number or "",
            callsign=ac.callsign or "",
        )
        rows.append((flight_id, self._title_font, self.theme.label))

        brand = marketing_brand_name(ac.flight_number or ac.callsign or "")
        airline_name = ac.airline or brand or ""
        if airline_name:
            rows.append((airline_name, self._body_font, self.theme.muted))

        if ac.origin and ac.destination:
            rows.append((f"{format_route_endpoint(ac.origin)}  →", self._body_font, self.theme.route))
            rows.append((format_route_endpoint(ac.destination), self._body_font, self.theme.route))
        elif ac.origin:
            rows.append((f"From {format_route_endpoint(ac.origin)}", self._body_font, self.theme.route))
        elif ac.destination:
            rows.append((f"To {format_route_endpoint(ac.destination)}", self._body_font, self.theme.route))

        meta_parts = []
        if ac.aircraft_type:
            meta_parts.append(ac.aircraft_type)
        if ac.distance_km is not None:
            d = km_to_unit(ac.distance_km, self.distance_unit)
            meta_parts.append(f"{d:.1f} {unit_label(self.distance_unit)}")
        if meta_parts:
            rows.append((" · ".join(meta_parts), self._detail_font, self.theme.muted))

        telemetry = []
        alt_str = format_altitude(ac.altitude_ft)
        if alt_str:
            telemetry.append(alt_str)
        if ac.ground_speed_kt is not None:
            telemetry.append(f"{ac.ground_speed_kt:.0f} kt")
        if ac.track_deg is not None:
            telemetry.append(f"HDG {ac.track_deg:.0f}°")
        if telemetry:
            rows.append((" · ".join(telemetry), self._detail_font, self.theme.info_text))

        if ac.vertical_rate_fpm:
            vr_color = altitude_tag_color(ac.vertical_rate_fpm, self.theme)
            rows.append((f"V/S {ac.vertical_rate_fpm:+,} fpm", self._detail_font, vr_color))

        if ac.squawk:
            sq_color = self.theme.emergency if ac.is_emergency else self.theme.muted
            rows.append((f"Squawk {ac.squawk}", self._detail_font, sq_color))

        if ac.registration:
            rows.append((ac.registration, self._detail_font, self.theme.hint))

        if ac.registered_owner:
            rows.append((ac.registered_owner, self._detail_font, self.theme.muted))

        if ac.photo_credit:
            rows.append((ac.photo_credit, self._detail_font, self.theme.hint))

        return rows

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)

        ac = self._current_aircraft()
        if ac is None:
            nav.draw_breadcrumb(surface, ["Radar", "Detail"], self.theme)
            nav.draw_footer_buttons(surface, _FOOTER_SINGLE, self.theme)
            draw_center_text(surface, "No traffic", scaling.center_y(), self._body_font, self.theme.muted)
            return

        crumb_label = display_flight_id(
            flight_number=ac.flight_number or "",
            callsign=ac.callsign or "",
        )
        nav.draw_breadcrumb(surface, ["Radar", "Flight", crumb_label], self.theme)

        total = len(self._aircraft_list) if self._aircraft_list else 1
        idx = self._find_index()
        nav.draw_page_dots(surface, idx, total, self.theme)

        chrome_top = nav.content_top_y(has_dots=total > 1)
        bottom = nav.content_bottom_y()
        line_gap = scaling.s(1)

        y = chrome_top - self._scroll.offset

        photo_info = get_photo_info(ac.icao_hex)
        if photo_info:
            max_h = scaling.s(72)
            max_w = int(scaling.visible_radius() * 1.45)
            photo = load_photo_surface(photo_info["path"], max_h, max_w=max_w, radius=scaling.s(8))
            if photo:
                rect = photo.get_rect(midtop=(scaling.center_x(), y))
                if rect.top >= chrome_top - max_h and rect.bottom <= bottom + max_h:
                    surface.blit(photo, rect)
                y += rect.height + scaling.s(4)

        rows = self._build_rows(ac)
        for text, font, color in rows:
            h = font.get_height()
            if chrome_top - h <= y <= bottom:
                draw_center_text(surface, text, int(y), font, color)
            y += h + line_gap

        if ac.is_emergency:
            y += scaling.s(6)
            if chrome_top <= y <= bottom:
                draw_center_text(surface, f"⚠ EMERGENCY {ac.squawk}", int(y), self._title_font, self.theme.emergency)

        total_h = y + self._scroll.offset - chrome_top
        self._scroll.max_offset = max(0, total_h - (bottom - chrome_top))

        buttons = _FOOTER_BUTTONS if len(self._aircraft_list) > 1 else _FOOTER_SINGLE
        nav.draw_footer_buttons(surface, buttons, self.theme)

    def handle_tap(self, x: int, y: int) -> str:
        """Returns 'radar' to go back, 'prev'/'next' to browse, '' to do nothing."""
        buttons = _FOOTER_BUTTONS if len(self._aircraft_list) > 1 else _FOOTER_SINGLE
        idx = nav.tap_footer_button(x, y, len(buttons))
        if idx is not None:
            action = buttons[idx]
            if action == "prev":
                self._navigate(-1)
                return ""
            if action == "next":
                self._navigate(1)
                return ""
            return "radar"

        breadcrumb_y = scaling.center_y() - int(scaling.visible_radius() * 0.75)
        if y < breadcrumb_y + scaling.s(30):
            return "radar"

        return ""

    def handle_scroll(self, delta: int) -> None:
        self._scroll.step(delta * scaling.s(36))

"""Flight detail screen — shows expanded info for a selected aircraft."""

from typing import Optional

import pygame

from flugradar.data_sources.geo import km_to_unit, unit_label
from flugradar.data_sources.models import Aircraft
from flugradar.display.fonts import get_font
from flugradar.display.theme import Theme


class DetailScreen:
    """Renders detailed flight information for a single aircraft."""

    def __init__(self, screen_size: int, theme: Theme, distance_unit: str = "km") -> None:
        self.size = screen_size
        self.theme = theme
        self.distance_unit = distance_unit
        self.aircraft: Optional[Aircraft] = None
        self._font: Optional[pygame.font.Font] = None
        self._font_lg: Optional[pygame.font.Font] = None
        self._font_num: Optional[pygame.font.Font] = None
        self._back_rect: Optional[pygame.Rect] = None

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = get_font(16)
            self._font_lg = get_font(28, bold=True)
            self._font_num = get_font(16, mono=True)

    def set_aircraft(self, ac: Aircraft) -> None:
        self.aircraft = ac

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)
        ac = self.aircraft
        if ac is None:
            return

        cx = self.size // 2
        y = 40

        title = self._font_lg.render(ac.display_label, True, self.theme.compass_text)
        surface.blit(title, (cx - title.get_width() // 2, y))
        y += 50

        lines: list[tuple[str, str, bool]] = []
        lines.append(("ICAO", ac.icao_hex.upper(), False))
        if ac.registration:
            lines.append(("Reg", ac.registration, False))
        if ac.aircraft_type:
            lines.append(("Type", ac.aircraft_type, False))
        if ac.airline:
            lines.append(("Airline", ac.airline, False))
        if ac.flight_number:
            lines.append(("Flight", ac.flight_number, False))
        if ac.origin and ac.destination:
            lines.append(("Route", f"{ac.origin} -> {ac.destination}", False))
        if ac.altitude_ft is not None:
            lines.append(("Altitude", f"{ac.altitude_ft:,} ft", True))
        if ac.ground_speed_kt is not None:
            lines.append(("Speed", f"{ac.ground_speed_kt:.0f} kt", True))
        if ac.track_deg is not None:
            lines.append(("Heading", f"{ac.track_deg:.0f}°", True))
        if ac.vertical_rate_fpm:
            lines.append(("V/S", f"{ac.vertical_rate_fpm:+,} fpm", True))
        if ac.squawk:
            lines.append(("Squawk", ac.squawk, True))
        if ac.distance_km is not None:
            d = km_to_unit(ac.distance_km, self.distance_unit)
            lines.append(("Distance", f"{d:.1f} {unit_label(self.distance_unit)}", True))
        if ac.bearing_deg is not None:
            lines.append(("Bearing", f"{ac.bearing_deg:.0f}°", True))

        for label, value, is_numeric in lines:
            lbl_surf = self._font.render(f"{label}:", True, self.theme.range_label)
            font = self._font_num if is_numeric else self._font
            val_surf = font.render(value, True, self.theme.info_text)
            surface.blit(lbl_surf, (60, y))
            surface.blit(val_surf, (200, y))
            y += 26

        if ac.is_emergency:
            y += 10
            warn = self._font_lg.render(
                f"EMERGENCY {ac.squawk}", True, self.theme.emergency
            )
            surface.blit(warn, (cx - warn.get_width() // 2, y))
            y += 40

        y = self.size - 50
        back = self._font.render("BACK", True, self.theme.compass_text)
        bx = cx - back.get_width() // 2
        surface.blit(back, (bx, y))
        self._back_rect = pygame.Rect(bx - 10, y - 5, back.get_width() + 20, back.get_height() + 10)

    def handle_tap(self, x: int, y: int) -> bool:
        if self._back_rect and self._back_rect.collidepoint(x, y):
            return True
        return False

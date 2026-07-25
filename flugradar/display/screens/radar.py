"""Main radar screen — draws the live flight radar view."""

from typing import Optional

import pygame

from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.projection import ScreenProjection
from flugradar.display.renderer import RadarRenderer
from flugradar.display.theme import Theme


class RadarScreen:
    """Composites all radar layers onto the display surface."""

    def __init__(
        self,
        screen_size: int,
        projection: ScreenProjection,
        theme: Theme,
        distance_unit: str = "km",
        aircraft_icon_set: str = "detailed",
        show_compass: bool = True,
        show_sweep: bool = True,
        show_aircraft_tags: bool = True,
        highlight_emergency: bool = True,
        highlight_military: bool = True,
    ) -> None:
        self.size = screen_size
        self.proj = projection
        self.show_compass = show_compass
        self.show_sweep = show_sweep
        self.renderer = RadarRenderer(
            screen_size=screen_size,
            projection=projection,
            theme=theme,
            distance_unit=distance_unit,
            aircraft_icon_set=aircraft_icon_set,
            show_aircraft_tags=show_aircraft_tags,
            highlight_emergency=highlight_emergency,
            highlight_military=highlight_military,
        )
        self.selected_hex: Optional[str] = None
        self._hit_rects: list[tuple[pygame.Rect, Aircraft]] = []

    def draw(
        self,
        surface: pygame.Surface,
        aircraft: list[Aircraft],
        has_map_bg: bool = False,
        weather_str: str = "",
        tracked_callsign: str = "",
    ) -> None:
        if not has_map_bg:
            self.renderer.draw_background(surface)
        self.renderer.draw_rings(surface)
        if self.show_compass:
            self.renderer.draw_compass(surface)
        self.renderer.draw_centre(surface)
        self._hit_rects = self.renderer.draw_aircraft(
            surface, aircraft, self.selected_hex, tracked_callsign
        )
        if self.show_sweep:
            self.renderer.draw_sweep(surface)
        self.renderer.draw_status_bar(
            surface, len(aircraft), self.proj.radius_km, weather_str
        )

    def handle_tap(self, x: int, y: int) -> Optional[Aircraft]:
        for rect, ac in self._hit_rects:
            if rect.collidepoint(x, y):
                self.selected_hex = ac.icao_hex
                return ac
        self.selected_hex = None
        return None

    def zoom(self, factor: float) -> None:
        new_radius = self.proj.radius_km * factor
        new_radius = max(5.0, min(500.0, new_radius))
        self.proj.radius_km = new_radius

    def update_theme(self, theme: Theme) -> None:
        self.renderer.theme = theme

    def update_unit(self, unit: str) -> None:
        self.renderer.distance_unit = unit

    def update_icon_set(self, icon_set: str) -> None:
        self.renderer.aircraft_icon_set = icon_set

    def update_display_options(
        self, show_compass: bool, show_sweep: bool, show_aircraft_tags: bool,
    ) -> None:
        self.show_compass = show_compass
        self.show_sweep = show_sweep
        self.renderer.show_aircraft_tags = show_aircraft_tags

    def update_highlight_options(
        self, highlight_emergency: bool, highlight_military: bool,
    ) -> None:
        self.renderer.highlight_emergency = highlight_emergency
        self.renderer.highlight_military = highlight_military

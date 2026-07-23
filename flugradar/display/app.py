"""Main pygame application loop for the radar display."""

import logging
import time
from enum import Enum, auto

import pygame

from flugradar.config.settings import AppSettings
from flugradar.data_sources.adsb_fi import AdsbFiClient
from flugradar.data_sources.demo import DemoSource
from flugradar.data_sources.enrichment import EnrichmentClient
from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.projection import ScreenProjection
from flugradar.data_sources.weather import WeatherClient
from flugradar.display.gestures import GestureRecogniser, GestureType
from flugradar.display.mask import CircularViewport
from flugradar.display.screens.about import AboutScreen
from flugradar.display.screens.clock import ClockScreen
from flugradar.display.screens.detail import DetailScreen
from flugradar.display.screens.radar import RadarScreen
from flugradar.display.screens.settings_screen import SettingsScreen
from flugradar.display.theme import THEMES
from flugradar.maps.compositor import MapCompositor
from flugradar.maps.tiles import TileManager

log = logging.getLogger(__name__)


class ActiveScreen(Enum):
    RADAR = auto()
    DETAIL = auto()
    CLOCK = auto()
    ABOUT = auto()
    SETTINGS = auto()


class RadarApp:
    """Top-level display application."""

    def __init__(
        self,
        settings: AppSettings,
        screen_size: int = 720,
        demo_mode: bool = False,
        enable_map: bool = True,
        round_mask: bool = True,
        rotation_deg: float = 0.0,
    ) -> None:
        self.settings = settings
        self.screen_size = screen_size
        self.demo_mode = demo_mode
        self.enable_map = enable_map
        self.round_mask = round_mask
        self.rotation_deg = rotation_deg
        self.running = False
        self._active = ActiveScreen.RADAR
        self._aircraft: list[Aircraft] = []
        self._last_fetch: float = 0.0
        self._weather_client: WeatherClient | None = None
        self._enrichment_client: EnrichmentClient | None = None
        self._last_interaction: float = 0.0

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption("Sasso Radar Tower")

        screen = pygame.display.set_mode(
            (self.screen_size, self.screen_size),
            pygame.RESIZABLE,
        )
        clock = pygame.time.Clock()

        theme = THEMES.get(
            getattr(self.settings, "theme", "dark"), THEMES["dark"]
        )

        proj = ScreenProjection(
            home_lat=self.settings.home.lat,
            home_lon=self.settings.home.lon,
            radius_km=self.settings.home.radius_km,
            screen_size=self.screen_size,
        )

        radar = RadarScreen(
            self.screen_size, proj, theme,
            distance_unit=self.settings.distance_unit,
        )
        detail = DetailScreen(
            self.screen_size, theme,
            distance_unit=self.settings.distance_unit,
        )
        clock_scr = ClockScreen(self.screen_size, theme)
        about = AboutScreen(self.screen_size, theme)
        settings_scr = SettingsScreen(self.screen_size, theme)
        gestures = GestureRecogniser()

        viewport = CircularViewport(self.screen_size, self.rotation_deg) if self.round_mask else None

        map_comp = None
        if self.enable_map:
            try:
                tile_mgr = TileManager(provider_key="carto_dark")
                map_comp = MapCompositor(tile_mgr, proj)
            except Exception:
                log.warning("Map tiles unavailable, running without map background")

        if self.demo_mode:
            client = DemoSource(self.settings.home, count=30)
        else:
            client = AdsbFiClient(self.settings.adsb, self.settings.home)

        if self.settings.tomorrow_api_key:
            self._weather_client = WeatherClient(
                api_key=self.settings.tomorrow_api_key,
                lat=self.settings.home.lat,
                lon=self.settings.home.lon,
            )

        if self.settings.airlabs_api_key:
            self._enrichment_client = EnrichmentClient(
                api_key=self.settings.airlabs_api_key,
            )

        self._last_interaction = time.monotonic()
        self.running = True
        log.info(
            "Starting radar: %.4f, %.4f radius=%.0fkm",
            self.settings.home.lat, self.settings.home.lon,
            self.settings.home.radius_km,
        )

        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            if self._active in (ActiveScreen.DETAIL, ActiveScreen.ABOUT,
                                                ActiveScreen.SETTINGS, ActiveScreen.CLOCK):
                                self._active = ActiveScreen.RADAR
                            else:
                                self.running = False
                            continue

                    gesture = gestures.process_event(event)
                    if gesture:
                        self._last_interaction = time.monotonic()
                        self._handle_gesture(
                            gesture, radar, detail, clock_scr, about, settings_scr, map_comp
                        )

                now = time.monotonic()

                if (
                    self.settings.auto_clock_s > 0
                    and self._active != ActiveScreen.CLOCK
                    and (now - self._last_interaction) >= self.settings.auto_clock_s
                ):
                    self._active = ActiveScreen.CLOCK
                if now - self._last_fetch >= self.settings.adsb.poll_interval_s:
                    self._aircraft = client.get_aircraft()
                    self._aircraft = [
                        ac for ac in self._aircraft
                        if (ac.altitude_ft or 0) >= self.settings.min_altitude_ft
                        or ac.is_on_ground
                    ]
                    if self._enrichment_client:
                        self._enrichment_client.enrich(self._aircraft)
                    self._last_fetch = now

                weather_status = ""
                if self._weather_client:
                    weather = self._weather_client.get_weather()
                    if weather:
                        clock_scr.set_weather(weather.temperature_str, weather.condition)
                        weather_status = weather.temperature_str

                if self._active == ActiveScreen.RADAR:
                    if map_comp:
                        map_comp.render(screen)
                    radar.draw(
                        screen, self._aircraft,
                        has_map_bg=map_comp is not None,
                        weather_str=weather_status,
                    )
                    if map_comp:
                        self._draw_attribution(screen, map_comp.tiles.attribution)
                elif self._active == ActiveScreen.DETAIL:
                    if detail.aircraft:
                        for ac in self._aircraft:
                            if ac.icao_hex == detail.aircraft.icao_hex:
                                detail.set_aircraft(ac)
                                break
                    detail.draw(screen)
                elif self._active == ActiveScreen.CLOCK:
                    clock_scr.draw(screen)
                elif self._active == ActiveScreen.ABOUT:
                    about.draw(screen)
                elif self._active == ActiveScreen.SETTINGS:
                    settings_scr.draw(screen)

                if viewport:
                    viewport.apply(screen)

                pygame.display.flip()
                clock.tick(30)

        except KeyboardInterrupt:
            pass
        finally:
            client.close()
            if self._enrichment_client:
                self._enrichment_client.close()
            if self._weather_client:
                self._weather_client.close()
            if map_comp:
                map_comp.tiles.close()
            pygame.quit()

    def _draw_attribution(self, surface: pygame.Surface, text: str) -> None:
        font = pygame.font.SysFont("sans", 11)
        txt = font.render(text, True, (100, 100, 100))
        x = self.screen_size - txt.get_width() - 8
        y = self.screen_size - txt.get_height() - 6
        surface.blit(txt, (x, y))

    def _handle_gesture(
        self, gesture, radar, detail, clock_scr, about, settings_scr, map_comp
    ) -> None:
        if self._active == ActiveScreen.RADAR:
            if gesture.type == GestureType.TAP:
                ac = radar.handle_tap(gesture.x, gesture.y)
                if ac:
                    detail.set_aircraft(ac)
                    self._active = ActiveScreen.DETAIL
            elif gesture.type == GestureType.ZOOM_IN:
                radar.zoom(0.8)
                if map_comp:
                    map_comp.invalidate()
            elif gesture.type == GestureType.ZOOM_OUT:
                radar.zoom(1.25)
                if map_comp:
                    map_comp.invalidate()
            elif gesture.type == GestureType.SWIPE_DOWN:
                self._active = ActiveScreen.CLOCK
            elif gesture.type == GestureType.SWIPE_UP:
                self._active = ActiveScreen.ABOUT
            elif gesture.type == GestureType.SWIPE_LEFT:
                self._active = ActiveScreen.SETTINGS

        elif self._active == ActiveScreen.DETAIL:
            if gesture.type == GestureType.TAP:
                if detail.handle_tap(gesture.x, gesture.y):
                    self._active = ActiveScreen.RADAR
            elif gesture.type in (GestureType.SWIPE_RIGHT, GestureType.SWIPE_DOWN):
                self._active = ActiveScreen.RADAR

        elif self._active == ActiveScreen.CLOCK:
            if gesture.type == GestureType.SWIPE_UP:
                self._active = ActiveScreen.RADAR
            elif gesture.type == GestureType.SWIPE_LEFT:
                self._active = ActiveScreen.SETTINGS

        elif self._active == ActiveScreen.ABOUT:
            if gesture.type == GestureType.TAP:
                if about.handle_tap(gesture.x, gesture.y):
                    self._active = ActiveScreen.RADAR
            elif gesture.type in (GestureType.SWIPE_DOWN, GestureType.SWIPE_RIGHT):
                self._active = ActiveScreen.RADAR

        elif self._active == ActiveScreen.SETTINGS:
            if gesture.type == GestureType.TAP:
                result = settings_scr.handle_tap(gesture.x, gesture.y)
                if result == "back":
                    self._active = ActiveScreen.RADAR
                elif result == "changed":
                    new_theme = THEMES.get(settings_scr.selected_theme)
                    if new_theme:
                        radar.update_theme(new_theme)
                    radar.update_unit(settings_scr.selected_unit)
            elif gesture.type == GestureType.SWIPE_RIGHT:
                self._active = ActiveScreen.RADAR

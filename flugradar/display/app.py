"""Main pygame application loop for the radar display."""

import logging
import time
from enum import Enum, auto

import pygame

from flugradar.config.settings import AppSettings
from flugradar.data_sources.adsb_fi import AdsbFiClient
from flugradar.data_sources.adsbdb import AdsbdbClient
from flugradar.data_sources.aircraft_photo import request_adsbdb_photo, request_photo
from flugradar.data_sources.demo import DemoSource
from flugradar.data_sources.enrichment import AdsbdbEnricher, EnrichmentClient, FlightEnrichment
from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.projection import ScreenProjection
from flugradar.data_sources.weather import WeatherClient
from flugradar.display import scaling
from flugradar.display.brightness import apply_dim_overlay, effective_brightness
from flugradar.display.fonts import get_font
from flugradar.display.gestures import GestureRecogniser, GestureType
from flugradar.display.mask import CircularViewport
from flugradar.display.screens.about import AboutScreen
from flugradar.display.screens.clock import ClockScreen
from flugradar.display.screens.detail import DetailScreen
from flugradar.display.screens.radar import RadarScreen
from flugradar.display.screens.menu import MenuScreen
from flugradar.display.theme import CLASSIC_AMBER, TOKENS, Theme, ease_out_cubic, resolve_theme
from flugradar.maps.compositor import MapCompositor
from flugradar.maps.rainviewer import RainViewerClient
from flugradar.maps.tiles import TileManager, resolve_provider_key

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
        self._flight_enrichment: FlightEnrichment | None = None
        self._rainviewer_client: RainViewerClient | None = None
        self._last_interaction: float = 0.0
        self._last_reload_check: float = 0.0
        self._theme: Theme | None = None
        self._prev_frame_copy: pygame.Surface | None = None
        self._transition_from: pygame.Surface | None = None
        self._transition_start: float = 0.0

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption("Sasso Radar Tower")

        scaling.init(self.screen_size)

        screen = pygame.display.set_mode(
            (self.screen_size, self.screen_size),
            pygame.RESIZABLE,
        )
        clock = pygame.time.Clock()

        theme = resolve_theme(getattr(self.settings, "theme", "amber"))
        self._theme = theme

        proj = ScreenProjection(
            home_lat=self.settings.home.lat,
            home_lon=self.settings.home.lon,
            radius_km=self.settings.home.radius_km,
            screen_size=self.screen_size,
        )

        radar = RadarScreen(
            self.screen_size, proj, theme,
            distance_unit=self.settings.distance_unit,
            aircraft_icon_set=self.settings.aircraft_icon_set,
            show_compass=self.settings.show_compass,
            show_sweep=self.settings.show_sweep,
            show_aircraft_tags=self.settings.show_aircraft_tags,
            highlight_emergency=self.settings.highlight_emergency,
            highlight_military=self.settings.highlight_military,
        )
        detail = DetailScreen(
            self.screen_size, theme,
            distance_unit=self.settings.distance_unit,
        )
        clock_scr = ClockScreen(self.screen_size, theme, time_format=self.settings.time_format)
        about = AboutScreen(
            self.screen_size, theme,
            openaip_enabled=self._openaip_enabled(),
            rainviewer_enabled=self._rainviewer_enabled(),
        )
        menu = MenuScreen(self.screen_size, theme, self.settings)
        gestures = GestureRecogniser()

        viewport = (
            CircularViewport(self.screen_size, self.rotation_deg, theme=theme)
            if self.round_mask else None
        )

        map_comp = None
        if self.enable_map:
            try:
                self._rainviewer_client = RainViewerClient()
                base_mgr = self._build_base_tile_manager()
                overlays = self._build_overlays()
                map_comp = MapCompositor(
                    base_mgr, proj, overlay_tiles=overlays,
                    brightness=self.settings.map_brightness / 100.0,
                )
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
            self._flight_enrichment = FlightEnrichment(
                airlabs_client=EnrichmentClient(api_key=self.settings.airlabs_api_key),
            )
        elif self.settings.adsbdb_enabled:
            self._flight_enrichment = FlightEnrichment(
                adsbdb_enricher=AdsbdbEnricher(AdsbdbClient()),
            )

        frame_surface = pygame.Surface((self.screen_size, self.screen_size))

        self._last_interaction = time.monotonic()
        self.running = True
        log.info(
            "Starting radar: %.4f, %.4f radius=%.0fkm",
            self.settings.home.lat, self.settings.home.lon,
            self.settings.home.radius_km,
        )

        try:
            while self.running:
                active_before = self._active
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
                            gesture, radar, detail, clock_scr, about, menu, map_comp,
                            proj, viewport,
                        )

                now = time.monotonic()

                if now - self._last_reload_check >= 2.0:
                    self._last_reload_check = now
                    if self.settings.check_portal_reload():
                        self._apply_live_settings(
                            proj, radar, detail, clock_scr, about,
                            menu, map_comp, viewport,
                        )

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
                    if self.settings.only_highlighted:
                        self._aircraft = [
                            ac for ac in self._aircraft
                            if ac.is_emergency or ac.is_military
                        ]
                    if self._flight_enrichment:
                        self._flight_enrichment.poll(
                            self._aircraft, nearest_limit=self.settings.adsbdb_enrich_nearest,
                        )
                    self._request_photos(self._aircraft)
                    self._update_photo_fields(self._aircraft)
                    self._last_fetch = now

                weather_status = ""
                if self._weather_client:
                    weather = self._weather_client.get_weather()
                    if weather:
                        temp_str = weather.temperature_str(self.settings.temperature_unit)
                        clock_scr.set_weather(temp_str, weather.condition)
                        weather_status = temp_str

                self._render_active_screen(
                    frame_surface, radar, detail, clock_scr, about, menu,
                    map_comp, weather_status,
                )

                if self._active != active_before:
                    self._transition_from = self._prev_frame_copy
                    self._transition_start = now

                self._compose_frame(screen, frame_surface)
                self._prev_frame_copy = frame_surface.copy()

                if viewport:
                    viewport.apply(screen)

                pygame.display.flip()
                clock.tick(30)

        except KeyboardInterrupt:
            pass
        finally:
            client.close()
            if self._flight_enrichment:
                self._flight_enrichment.close()
            if self._weather_client:
                self._weather_client.close()
            if map_comp:
                if map_comp.tiles is not None:
                    map_comp.tiles.close()
                for overlay in map_comp.overlay_tiles:
                    overlay.close()
            if self._rainviewer_client:
                self._rainviewer_client.close()
            pygame.quit()

    def _openaip_enabled(self) -> bool:
        return bool(self.settings.openaip_api_key and self.settings.openaip_overlay_enabled)

    def _rainviewer_enabled(self) -> bool:
        return bool(self.settings.rainviewer_enabled)

    def _build_base_tile_manager(self) -> TileManager | None:
        provider_key = resolve_provider_key(self.settings.map_provider)
        if provider_key == "none":
            return None
        return TileManager(provider_key=provider_key)

    def _build_overlays(self) -> list[TileManager]:
        overlays: list[TileManager] = []
        if self._openaip_enabled():
            overlays.append(TileManager(provider_key="openaip", api_key=self.settings.openaip_api_key))
        if self._rainviewer_enabled() and self._rainviewer_client:
            overlays.append(TileManager(
                provider_key="rainviewer",
                frame_path_provider=self._rainviewer_client.latest_frame_path,
            ))
        return overlays

    def _request_photos(self, aircraft: list[Aircraft]) -> None:
        for ac in aircraft:
            request_photo(ac.icao_hex, ac.registration or "")
            if (
                self.settings.aircraft_photos_enabled
                and self._flight_enrichment
                and self._flight_enrichment.using_adsbdb
            ):
                urls = self._flight_enrichment.get_adsbdb_photo_urls(ac.icao_hex)
                if urls:
                    thumb, full = urls
                    request_adsbdb_photo(ac.icao_hex, thumb, full)

    def _update_photo_fields(self, aircraft: list[Aircraft]) -> None:
        from flugradar.data_sources.aircraft_photo import get_photo_info
        for ac in aircraft:
            info = get_photo_info(ac.icao_hex)
            if info:
                ac.photo_path = info["path"]
                ac.photo_credit = info.get("credit", "")

    def _apply_live_settings(
        self, proj, radar, detail, clock_scr, about, menu, map_comp,
        viewport=None,
    ) -> None:
        """Hot-apply changed portal settings without restarting."""
        theme = resolve_theme(self.settings.theme)
        self._theme = theme
        radar.update_theme(theme)
        radar.update_unit(self.settings.distance_unit)
        radar.update_icon_set(self.settings.aircraft_icon_set)
        radar.update_display_options(
            self.settings.show_compass, self.settings.show_sweep,
            self.settings.show_aircraft_tags,
        )
        radar.update_highlight_options(
            self.settings.highlight_emergency, self.settings.highlight_military,
        )
        detail.theme = theme
        detail.distance_unit = self.settings.distance_unit
        clock_scr.theme = theme
        clock_scr.time_format = self.settings.time_format
        about.theme = theme
        about.openaip_enabled = self._openaip_enabled()
        about.rainviewer_enabled = self._rainviewer_enabled()
        menu.theme = theme
        if viewport:
            viewport.update_theme(theme)

        proj.home_lat = self.settings.home.lat
        proj.home_lon = self.settings.home.lon
        proj.radius_km = self.settings.home.radius_km

        if map_comp:
            if map_comp.tiles is not None:
                map_comp.tiles.close()
            for overlay in map_comp.overlay_tiles:
                overlay.close()
            map_comp.tiles = self._build_base_tile_manager()
            map_comp.overlay_tiles = self._build_overlays()
            map_comp.brightness = self.settings.map_brightness / 100.0
            map_comp.invalidate()

        log.info(
            "Live-reload: theme=%s unit=%s home=%.4f,%.4f radius=%.0f",
            self.settings.theme, self.settings.distance_unit,
            self.settings.home.lat, self.settings.home.lon,
            self.settings.home.radius_km,
        )

    def _render_active_screen(
        self, target, radar, detail, clock_scr, about, menu,
        map_comp, weather_status,
    ) -> None:
        """Draw whichever screen is active into `target` (not necessarily
        the visible display surface -- see `_compose_frame`)."""
        if self._active == ActiveScreen.RADAR:
            has_map_bg = map_comp is not None and (
                map_comp.tiles is not None or map_comp.overlay_tiles
            )
            if map_comp and has_map_bg:
                map_comp.render(target)
            radar.draw(
                target, self._aircraft,
                has_map_bg=has_map_bg,
                weather_str=weather_status,
            )
            if has_map_bg:
                self._draw_attribution(target, map_comp.attribution)
        elif self._active == ActiveScreen.DETAIL:
            detail.set_aircraft_list(self._aircraft)
            if detail.aircraft:
                for ac in self._aircraft:
                    if ac.icao_hex == detail.aircraft.icao_hex:
                        detail.set_aircraft(ac)
                        break
            detail.draw(target)
        elif self._active == ActiveScreen.CLOCK:
            clock_scr.draw(target)
        elif self._active == ActiveScreen.ABOUT:
            about.draw(target)
        elif self._active == ActiveScreen.SETTINGS:
            menu.draw(target)

    def _compose_frame(self, screen: pygame.Surface, frame: pygame.Surface) -> None:
        """Blit the freshly rendered `frame` onto `screen`, crossfading from
        the previous screen's last frame if a screen change just happened
        (Ausbaustufe 2 Schritt 3: all screen transitions share one duration
        and easing curve, taken from TOKENS)."""
        duration_s = TOKENS.duration_long_ms / 1000.0
        elapsed = time.monotonic() - self._transition_start
        if self._transition_from is not None and elapsed < duration_s:
            t = ease_out_cubic(elapsed / duration_s)
            screen.blit(self._transition_from, (0, 0))
            frame.set_alpha(int(255 * t))
            screen.blit(frame, (0, 0))
            frame.set_alpha(255)
        else:
            self._transition_from = None
            screen.blit(frame, (0, 0))

        apply_dim_overlay(screen, effective_brightness(self.settings))

    def _draw_attribution(self, surface: pygame.Surface, text: str) -> None:
        font = get_font(scaling.s(TOKENS.font_small))
        theme = self._theme
        colour = theme.hint if theme is not None else CLASSIC_AMBER.hint
        txt = font.render(text, True, colour)
        x = self.screen_size - txt.get_width() - 8
        y = self.screen_size - txt.get_height() - 6
        surface.blit(txt, (x, y))

    def _handle_gesture(
        self, gesture, radar, detail, clock_scr, about, menu, map_comp, proj, viewport
    ) -> None:
        if self._active == ActiveScreen.RADAR:
            if gesture.type == GestureType.TAP:
                ac = radar.handle_tap(gesture.x, gesture.y)
                if ac:
                    detail.set_aircraft(ac)
                    detail.set_aircraft_list(self._aircraft)
                    self._active = ActiveScreen.DETAIL
                    if self._flight_enrichment:
                        self._flight_enrichment.enrich_now(ac)
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
                result = detail.handle_tap(gesture.x, gesture.y)
                if result == "radar":
                    self._active = ActiveScreen.RADAR
            elif gesture.type in (GestureType.SWIPE_RIGHT, GestureType.SWIPE_DOWN):
                self._active = ActiveScreen.RADAR
            elif gesture.type == GestureType.SWIPE_UP:
                detail.handle_scroll(1)
            elif gesture.type == GestureType.SWIPE_LEFT:
                detail.handle_scroll(-1)

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
                result = menu.handle_tap(gesture.x, gesture.y)
                if result == "radar":
                    self._active = ActiveScreen.RADAR
                elif result == "changed":
                    # The menu already wrote settings.json itself (Schritt 4,
                    # 4.5: saved immediately, no save button). Apply it to
                    # the live screens right away instead of waiting for the
                    # 2s portal-reload poll, and mark the file as "already
                    # seen" so that poll doesn't redundantly re-apply our
                    # own write a moment later (which would flicker the map).
                    self.settings.mark_portal_synced()
                    self._apply_live_settings(
                        proj, radar, detail, clock_scr, about, menu, map_comp, viewport,
                    )
            elif gesture.type == GestureType.SWIPE_RIGHT:
                if menu.go_back() == "radar":
                    self._active = ActiveScreen.RADAR
            elif gesture.type == GestureType.SWIPE_UP:
                menu.handle_scroll(1)
            elif gesture.type == GestureType.SWIPE_DOWN:
                menu.handle_scroll(-1)

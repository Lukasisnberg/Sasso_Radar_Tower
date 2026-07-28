"""Main pygame application loop for the radar display."""

import logging
import time
from enum import Enum, auto
from typing import Callable, Optional

import pygame

from flugradar.config.locations import location_display_name
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
from flugradar.display.screens.tracking import TrackedFlightScreen
from flugradar.display.screens.weather import WeatherScreen
from flugradar.display.screens.wifi import WifiScreen
from flugradar.display.theme import CLASSIC_AMBER, TOKENS, Theme, ease_out_cubic, resolve_theme
from flugradar.maps.compositor import MapCompositor
from flugradar.maps.rainviewer import RainViewerClient
from flugradar.maps.tiles import TileManager, resolve_provider_key
from flugradar.system import network

log = logging.getLogger(__name__)

# After the user manually backs out of an *automatically* opened WLAN
# screen without connecting (still genuinely disconnected), don't bounce
# them right back into it on the very next poll -- give them the same
# breathing room the outage-tolerance window itself represents.
_WIFI_DISMISS_COOLDOWN_S = 300.0


class ActiveScreen(Enum):
    RADAR = auto()
    DETAIL = auto()
    CLOCK = auto()
    ABOUT = auto()
    SETTINGS = auto()
    TRACKING = auto()
    WEATHER = auto()
    WIFI = auto()


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
        on_first_frame: Optional[Callable[[], None]] = None,
    ) -> None:
        self.settings = settings
        self.screen_size = screen_size
        self.demo_mode = demo_mode
        self.enable_map = enable_map
        self.round_mask = round_mask
        self.rotation_deg = rotation_deg
        # Called once, right after the very first frame is actually drawn
        # to the screen -- e.g. the kiosk boot flow uses this to end the
        # Plymouth splash exactly when there's something to hand off to,
        # rather than at process start (see flugradar/main.py). Never
        # raises: a broken/missing callback must not take the render loop
        # down with it.
        self._on_first_frame = on_first_frame
        self._first_frame_done = False
        self.running = False
        self._active = ActiveScreen.RADAR
        self._aircraft: list[Aircraft] = []
        self._last_fetch: float = 0.0
        self._weather_client: WeatherClient | None = None
        self._flight_enrichment: FlightEnrichment | None = None
        self._rainviewer_client: RainViewerClient | None = None
        self._last_interaction: float = 0.0
        self._last_reload_check: float = 0.0
        self._last_wifi_check: float = 0.0
        self._wifi_dismissed_until: float | None = None
        self._theme: Theme | None = None
        self._prev_frame_copy: pygame.Surface | None = None
        self._transition_from: pygame.Surface | None = None
        self._transition_start: float = 0.0
        # Tracked-flight lifecycle (Ausbaustufe 2, Schritt 5) -- kept here,
        # not on TrackedFlightScreen, since it must keep running even while
        # a different screen is on-screen (e.g. ending tracking on timeout
        # while the user is looking at the clock).
        self._tracked_last_seen: float | None = None
        self._tracked_was_airborne: bool = False
        self._tracked_last_snapshot: Aircraft | None = None

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
            show_rings=self.settings.show_rings,
            show_aircraft_tags=self.settings.show_aircraft_tags,
            highlight_emergency=self.settings.highlight_emergency,
            highlight_military=self.settings.highlight_military,
        )
        detail = DetailScreen(
            self.screen_size, theme,
            distance_unit=self.settings.distance_unit,
        )
        detail.tracked_callsign = self.settings.tracked_callsign
        clock_scr = ClockScreen(self.screen_size, theme, time_format=self.settings.time_format)
        about = AboutScreen(
            self.screen_size, theme,
            openaip_enabled=self._openaip_enabled(),
            rainviewer_enabled=self._rainviewer_enabled(),
        )
        menu = MenuScreen(self.screen_size, theme, self.settings)
        tracking_scr = TrackedFlightScreen(
            self.screen_size, theme,
            distance_unit=self.settings.distance_unit,
            aircraft_icon_set=self.settings.aircraft_icon_set,
        )
        weather_scr = WeatherScreen(
            self.screen_size, theme,
            temperature_unit=self.settings.temperature_unit,
            distance_unit=self.settings.distance_unit,
            time_format=self.settings.time_format,
            location_label=location_display_name(self.settings.home.lat, self.settings.home.lon),
        )
        wifi_scr = WifiScreen(self.screen_size, theme)
        gestures = GestureRecogniser(self.screen_size)

        if self.settings.tracked_callsign:
            self._tracked_last_seen = time.monotonic()

        # If the network watchdog already flagged a missing connection
        # before this process even started (e.g. it had a head start
        # during boot), go straight to the WLAN screen instead of briefly
        # showing the radar with no data first.
        initial_wifi_status = network.read_status()
        if initial_wifi_status and initial_wifi_status.get("state") == network.SetupState.NEEDS_WIFI:
            self._active = ActiveScreen.WIFI
            wifi_scr.start_scan()

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
                                                ActiveScreen.SETTINGS, ActiveScreen.CLOCK,
                                                ActiveScreen.TRACKING, ActiveScreen.WEATHER):
                                self._active = ActiveScreen.RADAR
                            else:
                                self.running = False
                            continue

                    gesture = gestures.process_event(event)
                    if gesture:
                        self._last_interaction = time.monotonic()
                        self._handle_gesture(
                            gesture, radar, detail, clock_scr, about, menu, tracking_scr,
                            weather_scr, wifi_scr, map_comp, proj, viewport,
                        )

                now = time.monotonic()

                if now - self._last_reload_check >= 2.0:
                    self._last_reload_check = now
                    old_tracked = self.settings.tracked_callsign
                    if self.settings.check_portal_reload():
                        self._apply_live_settings(
                            proj, radar, detail, clock_scr, about,
                            menu, tracking_scr, weather_scr, wifi_scr, map_comp, viewport,
                        )
                        if self.settings.tracked_callsign != old_tracked:
                            self._reset_tracking_lifecycle()

                if now - self._last_wifi_check >= 2.0:
                    self._last_wifi_check = now
                    self._poll_wifi_status(wifi_scr, now)

                # Drains background scan/connect results every frame (not
                # gated by the 2s poll above) so the UI reacts promptly;
                # exiting back to radar on a successful manual connect is
                # handled locally here rather than through the shared
                # status file, since it all happened in this process.
                wifi_scr.update(now)
                if self._active == ActiveScreen.WIFI and wifi_scr.connected_recently(now):
                    self._active = ActiveScreen.RADAR

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
                    if self.settings.tracked_callsign:
                        self._update_tracking_lifecycle(now)

                weather_status = ""
                if self._weather_client:
                    weather = self._weather_client.get_weather()
                    if weather:
                        temp_str = weather.temperature_str(self.settings.temperature_unit)
                        clock_scr.set_weather(temp_str, weather.condition)
                        weather_status = temp_str

                self._render_active_screen(
                    frame_surface, radar, detail, clock_scr, about, menu, tracking_scr,
                    weather_scr, wifi_scr, map_comp, weather_status,
                )

                if self._active != active_before:
                    self._transition_from = self._prev_frame_copy
                    self._transition_start = now

                self._compose_frame(screen, frame_surface)
                self._prev_frame_copy = frame_surface.copy()

                if viewport:
                    # The bezel ring is the round panel's decorative edge and
                    # stays on for every other screen -- it's only tied to
                    # show_rings on the radar screen itself, where it visually
                    # doubles as the outermost distance ring.
                    show_bezel = not (
                        self._active == ActiveScreen.RADAR and not self.settings.show_rings
                    )
                    viewport.apply(screen, show_bezel=show_bezel)

                pygame.display.flip()

                if not self._first_frame_done:
                    self._first_frame_done = True
                    if self._on_first_frame:
                        try:
                            self._on_first_frame()
                        except Exception:
                            log.exception("on_first_frame callback failed -- continuing")

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

    def _find_tracked_aircraft(self) -> Aircraft | None:
        cs = self.settings.tracked_callsign.strip().upper()
        if not cs:
            return None
        for ac in self._aircraft:
            if (ac.callsign or "").strip().upper() == cs:
                return ac
        return None

    def _update_tracking_lifecycle(self, now: float) -> None:
        """Runs once per ADS-B poll, regardless of which screen is showing,
        so a timeout/landing can end tracking even while the user is
        looking at something else (Schritt 5, 5.3/5.1)."""
        match = self._find_tracked_aircraft()
        if match is not None:
            self._tracked_last_seen = now
            self._tracked_last_snapshot = match
            if not match.is_on_ground:
                self._tracked_was_airborne = True
            elif self._tracked_was_airborne:
                # was airborne, now on the ground again -- landed
                self._end_tracking()
                return

        if (
            self._tracked_last_seen is not None
            and (now - self._tracked_last_seen) >= self.settings.tracking_timeout_s
        ):
            self._end_tracking()

    def _update_tracking_screen(self, tracking_scr) -> None:
        """Feed the tracked-flight screen either the live aircraft object,
        or the last-known snapshot with an age if it's currently out of
        reception range (5.3) -- never crashes into an empty screen even
        if nothing has ever been received for this callsign yet."""
        match = self._find_tracked_aircraft()
        if match is not None:
            tracking_scr.set_tracking(match, True, None)
            return
        if self._tracked_last_snapshot is not None and self._tracked_last_seen is not None:
            age = time.monotonic() - self._tracked_last_seen
            tracking_scr.set_tracking(self._tracked_last_snapshot, False, age)
            return
        tracking_scr.set_tracking(None, False, None)

    def _update_weather_screen(self, weather_scr) -> None:
        """Feed the weather screen from the shared WeatherClient -- the
        screen adds no data source of its own. get_weather() already
        falls back to the last cached value on a failed fetch rather
        than raising, so `current` here is only None if nothing has ever
        been fetched successfully."""
        has_key = bool(self.settings.tomorrow_api_key)
        current = None
        is_stale = False
        age_s = None
        forecast: list = []
        if self._weather_client:
            current = self._weather_client.get_weather()
            is_stale = self._weather_client.is_stale
            age_s = self._weather_client.weather_age_s()
            forecast = self._weather_client.get_forecast(days=5)
        weather_scr.set_data(has_key, current, is_stale, age_s, forecast)

    def _start_tracking(self, callsign: str) -> None:
        self.settings.save_portal_settings({"tracked_callsign": callsign})
        self.settings.mark_portal_synced()
        self._reset_tracking_lifecycle()

    def _end_tracking(self) -> None:
        self.settings.save_portal_settings({"tracked_callsign": ""})
        self.settings.mark_portal_synced()
        self._reset_tracking_lifecycle()
        if self._active == ActiveScreen.TRACKING:
            self._active = ActiveScreen.RADAR

    def _reset_tracking_lifecycle(self) -> None:
        self._tracked_was_airborne = False
        self._tracked_last_snapshot = None
        self._tracked_last_seen = time.monotonic() if self.settings.tracked_callsign else None

    def _apply_live_settings(
        self, proj, radar, detail, clock_scr, about, menu, tracking_scr, weather_scr,
        wifi_scr, map_comp, viewport=None,
    ) -> None:
        """Hot-apply changed portal settings without restarting."""
        theme = resolve_theme(self.settings.theme)
        self._theme = theme
        radar.update_theme(theme)
        radar.update_unit(self.settings.distance_unit)
        radar.update_icon_set(self.settings.aircraft_icon_set)
        radar.update_display_options(
            self.settings.show_compass, self.settings.show_sweep,
            self.settings.show_rings, self.settings.show_aircraft_tags,
        )
        radar.update_highlight_options(
            self.settings.highlight_emergency, self.settings.highlight_military,
        )
        detail.theme = theme
        detail.distance_unit = self.settings.distance_unit
        detail.tracked_callsign = self.settings.tracked_callsign
        clock_scr.theme = theme
        clock_scr.time_format = self.settings.time_format
        about.theme = theme
        about.openaip_enabled = self._openaip_enabled()
        about.rainviewer_enabled = self._rainviewer_enabled()
        menu.theme = theme
        tracking_scr.theme = theme
        tracking_scr.distance_unit = self.settings.distance_unit
        tracking_scr.aircraft_icon_set = self.settings.aircraft_icon_set
        weather_scr.theme = theme
        weather_scr.temperature_unit = self.settings.temperature_unit
        weather_scr.distance_unit = self.settings.distance_unit
        weather_scr.time_format = self.settings.time_format
        weather_scr.location_label = location_display_name(self.settings.home.lat, self.settings.home.lon)
        wifi_scr.theme = theme
        if viewport:
            viewport.update_theme(theme)

        proj.home_lat = self.settings.home.lat
        proj.home_lon = self.settings.home.lon
        proj.radius_km = self.settings.home.radius_km

        if self._weather_client:
            self._weather_client.close()
            self._weather_client = None
        if self.settings.tomorrow_api_key:
            self._weather_client = WeatherClient(
                api_key=self.settings.tomorrow_api_key,
                lat=self.settings.home.lat,
                lon=self.settings.home.lon,
            )

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

    def _poll_wifi_status(self, wifi_scr, now: float) -> None:
        """Reads the shared status file the network watchdog service
        writes to (flugradar/system/network.py) and forces a screen
        switch into the WLAN screen for the automatic boot/outage case --
        independent of the normal swipe order, same idea as
        auto-returning to the clock screen on inactivity. Exiting back to
        radar on a successful connect is handled locally in the main loop
        instead (wifi_scr.connected_recently()), since that happens in
        this same process and doesn't need the round-trip through this
        file."""
        status = network.read_status()
        if status is None:
            return
        if status.get("state") != network.SetupState.NEEDS_WIFI:
            return
        if self._wifi_dismissed_until is not None and now < self._wifi_dismissed_until:
            return
        if self._active != ActiveScreen.WIFI:
            self._active = ActiveScreen.WIFI
            wifi_scr.start_scan()

    def _render_active_screen(
        self, target, radar, detail, clock_scr, about, menu, tracking_scr, weather_scr,
        wifi_scr, map_comp, weather_status,
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
                tracked_callsign=self.settings.tracked_callsign,
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
        elif self._active == ActiveScreen.TRACKING:
            self._update_tracking_screen(tracking_scr)
            tracking_scr.draw(target)
        elif self._active == ActiveScreen.WEATHER:
            self._update_weather_screen(weather_scr)
            weather_scr.draw(target)
        elif self._active == ActiveScreen.WIFI:
            wifi_scr.draw(target)

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
        self, gesture, radar, detail, clock_scr, about, menu, tracking_scr, weather_scr,
        wifi_scr, map_comp, proj, viewport,
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
            elif gesture.type == GestureType.SWIPE_RIGHT:
                self._active = ActiveScreen.TRACKING

        elif self._active == ActiveScreen.DETAIL:
            if gesture.type == GestureType.TAP:
                result = detail.handle_tap(gesture.x, gesture.y)
                if result == "radar":
                    self._active = ActiveScreen.RADAR
                elif result == "track":
                    ac = detail.aircraft
                    if ac and ac.callsign:
                        self._start_tracking(ac.callsign)
                        detail.tracked_callsign = self.settings.tracked_callsign
                        self._active = ActiveScreen.TRACKING
                elif result == "untrack":
                    self._end_tracking()
                    detail.tracked_callsign = self.settings.tracked_callsign
            elif gesture.type in (GestureType.SWIPE_RIGHT, GestureType.SWIPE_DOWN):
                self._active = ActiveScreen.RADAR
            elif gesture.type == GestureType.SWIPE_UP:
                detail.handle_scroll(1)
            elif gesture.type == GestureType.SWIPE_LEFT:
                detail.handle_scroll(-1)

        elif self._active == ActiveScreen.TRACKING:
            if gesture.type == GestureType.TAP:
                result = tracking_scr.handle_tap(gesture.x, gesture.y)
                if result == "stop":
                    self._end_tracking()
                    detail.tracked_callsign = self.settings.tracked_callsign
                elif result == "radar":
                    self._active = ActiveScreen.RADAR
            elif gesture.type in (GestureType.SWIPE_RIGHT, GestureType.SWIPE_DOWN):
                self._active = ActiveScreen.RADAR

        elif self._active == ActiveScreen.CLOCK:
            if gesture.type == GestureType.SWIPE_UP:
                self._active = ActiveScreen.RADAR
            elif gesture.type == GestureType.SWIPE_LEFT:
                self._active = ActiveScreen.SETTINGS
            elif gesture.type == GestureType.SWIPE_RIGHT:
                self._active = ActiveScreen.WEATHER

        elif self._active == ActiveScreen.WEATHER:
            if gesture.type == GestureType.TAP:
                result = weather_scr.handle_tap(gesture.x, gesture.y)
                if result == "radar":
                    self._active = ActiveScreen.RADAR
            elif gesture.type in (GestureType.SWIPE_LEFT, GestureType.SWIPE_DOWN):
                self._active = ActiveScreen.CLOCK

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
                        proj, radar, detail, clock_scr, about, menu, tracking_scr, weather_scr,
                        wifi_scr, map_comp, viewport,
                    )
                elif result == "wifi_setup":
                    # Manual trigger ("WLAN einrichten") -- runs in this
                    # same process, so switches straight over instead of
                    # going through the shared status file like the
                    # automatic boot/outage detection has to.
                    self._active = ActiveScreen.WIFI
                    wifi_scr.start_scan()
            elif gesture.type == GestureType.SWIPE_RIGHT:
                if menu.go_back() == "radar":
                    self._active = ActiveScreen.RADAR
            elif gesture.type == GestureType.SWIPE_UP:
                menu.handle_scroll(1)
            elif gesture.type == GestureType.SWIPE_DOWN:
                menu.handle_scroll(-1)

        elif self._active == ActiveScreen.WIFI:
            if gesture.type == GestureType.TAP:
                result = wifi_scr.handle_tap(gesture.x, gesture.y)
                if result == "radar":
                    status = network.read_status()
                    if status and status.get("state") == network.SetupState.NEEDS_WIFI:
                        # Backed out without connecting while genuinely
                        # still disconnected -- don't let the very next
                        # poll immediately bounce back into this screen.
                        self._wifi_dismissed_until = time.monotonic() + _WIFI_DISMISS_COOLDOWN_S
                    self._active = ActiveScreen.RADAR
            elif gesture.type == GestureType.SWIPE_UP:
                wifi_scr.handle_scroll(1)
            elif gesture.type == GestureType.SWIPE_DOWN:
                wifi_scr.handle_scroll(-1)

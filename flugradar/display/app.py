"""Main pygame application loop for the radar display."""

import logging
import sys
import time
from enum import Enum, auto
from typing import Optional

import pygame

from flugradar.config.settings import AppSettings
from flugradar.data_sources.adsb_fi import AdsbFiClient
from flugradar.data_sources.demo import DemoSource
from flugradar.data_sources.models import Aircraft
from flugradar.data_sources.projection import ScreenProjection
from flugradar.display.gestures import GestureRecogniser, GestureType
from flugradar.display.screens.detail import DetailScreen
from flugradar.display.screens.radar import RadarScreen
from flugradar.display.theme import THEMES

log = logging.getLogger(__name__)

_ZOOM_PRESETS_KM = [25, 50, 100, 150, 250, 400]


class ActiveScreen(Enum):
    RADAR = auto()
    DETAIL = auto()


class RadarApp:
    """Top-level display application."""

    def __init__(
        self,
        settings: AppSettings,
        screen_size: int = 720,
        demo_mode: bool = False,
    ) -> None:
        self.settings = settings
        self.screen_size = screen_size
        self.demo_mode = demo_mode
        self.running = False
        self._active = ActiveScreen.RADAR
        self._zoom_idx = _ZOOM_PRESETS_KM.index(
            min(_ZOOM_PRESETS_KM, key=lambda z: abs(z - settings.home.radius_km))
        )
        self._aircraft: list[Aircraft] = []
        self._last_fetch: float = 0.0

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption("Sasso Radar Tower")

        screen = pygame.display.set_mode(
            (self.screen_size, self.screen_size),
            pygame.RESIZABLE,
        )
        clock = pygame.time.Clock()

        theme = THEMES.get(
            self.settings.distance_unit, THEMES["dark"]
        )
        theme = THEMES["dark"]

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
        gestures = GestureRecogniser()

        if self.demo_mode:
            client = DemoSource(self.settings.home, count=30)
        else:
            client = AdsbFiClient(self.settings.adsb, self.settings.home)

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
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        if self._active == ActiveScreen.DETAIL:
                            self._active = ActiveScreen.RADAR
                        else:
                            self.running = False
                        continue

                    gesture = gestures.process_event(event)
                    if gesture:
                        self._handle_gesture(gesture, radar, detail)

                now = time.monotonic()
                if now - self._last_fetch >= self.settings.adsb.poll_interval_s:
                    self._aircraft = client.get_aircraft()
                    self._aircraft = [
                        ac for ac in self._aircraft
                        if (ac.altitude_ft or 0) >= self.settings.min_altitude_ft
                        or ac.is_on_ground
                    ]
                    self._last_fetch = now

                if self._active == ActiveScreen.RADAR:
                    radar.draw(screen, self._aircraft)
                elif self._active == ActiveScreen.DETAIL:
                    if detail.aircraft:
                        for ac in self._aircraft:
                            if ac.icao_hex == detail.aircraft.icao_hex:
                                detail.set_aircraft(ac)
                                break
                    detail.draw(screen)

                pygame.display.flip()
                clock.tick(30)

        except KeyboardInterrupt:
            pass
        finally:
            client.close()
            pygame.quit()

    def _handle_gesture(
        self,
        gesture,
        radar: RadarScreen,
        detail: DetailScreen,
    ) -> None:
        if self._active == ActiveScreen.RADAR:
            if gesture.type == GestureType.TAP:
                ac = radar.handle_tap(gesture.x, gesture.y)
                if ac:
                    detail.set_aircraft(ac)
                    self._active = ActiveScreen.DETAIL
            elif gesture.type == GestureType.ZOOM_IN:
                radar.zoom(0.8)
            elif gesture.type == GestureType.ZOOM_OUT:
                radar.zoom(1.25)

        elif self._active == ActiveScreen.DETAIL:
            if gesture.type == GestureType.TAP:
                if detail.handle_tap(gesture.x, gesture.y):
                    self._active = ActiveScreen.RADAR
            elif gesture.type in (GestureType.SWIPE_RIGHT, GestureType.SWIPE_DOWN):
                self._active = ActiveScreen.RADAR

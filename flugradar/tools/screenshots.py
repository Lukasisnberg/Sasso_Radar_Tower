"""Headless screenshot harness for every screen (Schritt 0 of the UI overhaul).

Renders each screen with plausible demo data at 720x720, composited through
the same mask/bezel/dim-overlay path RadarApp.run() uses live (see
flugradar/display/app.py: `_compose_frame` + `CircularViewport.apply`), so
the output PNGs match what the device actually shows. Does not construct or
run a RadarApp instance -- that would pull in real network polling (ADS-B,
weather, map tiles, wifi scan/connect threads); the individual screen
objects are built directly instead, mirroring run()'s construction sequence.

Usage: python -m flugradar.tools.screenshots [--theme amber|mono] [--out-dir docs/ui]
"""

import argparse
import os
from pathlib import Path
from typing import Callable

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from flugradar.config.locations import location_display_name
from flugradar.config.settings import AppSettings, HomeLocation
from flugradar.data_sources.demo import DemoSource
from flugradar.data_sources.projection import ScreenProjection
from flugradar.data_sources.weather import DailyForecast, WeatherData
from flugradar.display import nav, scaling
from flugradar.display.brightness import apply_dim_overlay, effective_brightness
from flugradar.display.mask import CircularViewport
from flugradar.display.screens.about import AboutScreen
from flugradar.display.screens.clock import ClockScreen
from flugradar.display.screens.detail import DetailScreen
from flugradar.display.screens.menu import MenuScreen
from flugradar.display.screens.radar import RadarScreen
from flugradar.display.screens.tracking import TrackedFlightScreen
from flugradar.display.screens.weather import WeatherScreen
from flugradar.display.screens.wifi import WifiScreen
from flugradar.display.theme import resolve_theme
from flugradar.system.network import NetworkInfo

SCREEN_SIZE = 720


def _demo_forecast() -> list[DailyForecast]:
    conditions = ["Bewölkt", "Sonnig", "Regen", "Bewölkt", "Sonnig"]
    return [
        DailyForecast(
            date=f"2026-08-{22 + i:02d}",
            temp_min_c=12 + i,
            temp_max_c=22 + i,
            weather_code=1,
            condition=conditions[i],
        )
        for i in range(5)
    ]


def _compose_and_save(
    frame: pygame.Surface, viewport: CircularViewport, settings: AppSettings, out_path: Path,
) -> None:
    """Mirror RadarApp._compose_frame + viewport.apply for one still frame --
    no crossfade, since there is no previous frame in a one-shot harness."""
    screen = pygame.Surface((SCREEN_SIZE, SCREEN_SIZE))
    screen.blit(frame, (0, 0))
    apply_dim_overlay(screen, effective_brightness(settings))
    viewport.apply(screen, show_bezel=True)
    pygame.image.save(screen, str(out_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=["amber", "mono"], default="amber")
    parser.add_argument("--out-dir", default="docs/ui")
    args = parser.parse_args()

    pygame.init()
    pygame.display.set_mode((SCREEN_SIZE, SCREEN_SIZE))
    scaling.init(SCREEN_SIZE)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    theme = resolve_theme(args.theme)
    settings = AppSettings()
    viewport = CircularViewport(SCREEN_SIZE, theme=theme)

    home = HomeLocation()
    aircraft = DemoSource(home, count=12).get_aircraft()
    selected = aircraft[0]

    proj = ScreenProjection(
        home_lat=home.lat, home_lon=home.lon, radius_km=home.radius_km, screen_size=SCREEN_SIZE,
    )

    print(f"Rendering screens ({args.theme}) to {out_dir}/ ...")

    def shoot(name: str, draw: Callable[[pygame.Surface], None]) -> None:
        frame = pygame.Surface((SCREEN_SIZE, SCREEN_SIZE))
        draw(frame)
        _compose_and_save(frame, viewport, settings, out_dir / f"{name}.png")
        print(f"  {name}.png")

    radar = RadarScreen(SCREEN_SIZE, proj, theme)
    shoot("radar", lambda f: radar.draw(
        f, aircraft, has_map_bg=False, weather_str="21°C", tracked_callsign="",
    ))

    detail = DetailScreen(SCREEN_SIZE, theme)
    detail.set_aircraft_list(aircraft)
    detail.set_aircraft(selected)
    shoot("detail", detail.draw)

    detail.tracked_callsign = selected.callsign or ""
    shoot("detail_tracked", detail.draw)

    # Footer-button style comparison (Schritt 2, Rueckfrage im Auftrag:
    # "Footer-Buttons: mit oder ohne Flaeche") -- render the same screen
    # with both ui.button.Button variants so they can be compared side by
    # side before nav.py's default ("flat") is settled. Restores nav's
    # module-level default afterwards so the rest of this run is
    # unaffected.
    original_variant = nav._FOOTER_BUTTON_VARIANT
    for variant in ("flat", "filled"):
        nav._FOOTER_BUTTON_VARIANT = variant
        shoot(f"detail_buttons_{variant}", detail.draw)
    nav._FOOTER_BUTTON_VARIANT = original_variant

    clock_scr = ClockScreen(SCREEN_SIZE, theme)
    clock_scr.set_weather("18°C", "Bewölkt")
    shoot("clock", clock_scr.draw)

    about = AboutScreen(SCREEN_SIZE, theme, openaip_enabled=True, rainviewer_enabled=True)
    shoot("about", about.draw)

    menu = MenuScreen(SCREEN_SIZE, theme, settings)
    shoot("settings", menu.draw)

    tracking_scr = TrackedFlightScreen(SCREEN_SIZE, theme)
    tracking_scr.set_tracking(selected, True, None)
    shoot("tracking", tracking_scr.draw)

    # Second variant: nothing currently tracked -- one of the "missing
    # optional data" states the brief explicitly wants captured, not just
    # the happy path.
    tracking_scr.set_tracking(None, False, None)
    shoot("tracking_no_flight", tracking_scr.draw)

    weather_scr = WeatherScreen(
        SCREEN_SIZE, theme, location_label=location_display_name(home.lat, home.lon),
    )
    current = WeatherData(
        temperature_c=18.5, humidity=64, wind_speed_ms=3.2, wind_direction_deg=210,
        weather_code=1, condition="Bewölkt", temperature_apparent_c=17.0,
        precipitation_probability_pct=20,
    )
    weather_scr.set_data(True, current, False, 30.0, _demo_forecast())
    shoot("weather", weather_scr.draw)

    # Bypasses the real nmcli scan thread (network.scan_networks() talks to
    # NetworkManager, unavailable and pointless in a headless screenshot
    # run) by feeding the same NetworkInfo shape start_scan() would produce
    # directly into the screen's private state.
    wifi_scr = WifiScreen(SCREEN_SIZE, theme)
    wifi_scr._mode = "list"
    wifi_scr._networks = [
        NetworkInfo("HomeNet", 90, True, True),
        NetworkInfo("Nachbar_5G", 45, True, False),
        NetworkInfo("Free_WiFi", 20, False, False),
    ]
    shoot("wifi", wifi_scr.draw)

    pygame.quit()
    print("Done.")


if __name__ == "__main__":
    main()

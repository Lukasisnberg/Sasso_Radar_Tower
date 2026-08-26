"""Headless-Renderer für die Buch-Screenshots.

Rendert jeden Geräte-Screen mit `SDL_VIDEODRIVER=dummy` in 720x720 -- echte
Schriften, echtes Theme, keine Netzwerk-/Displayabhängigkeit. Folgt dem
bereits im Testcode etablierten Muster (siehe z. B.
`flugradar/tests/test_detail_route.py`, `test_weather_screen.py`,
`test_menu.py`), nur außerhalb von pytest und mit dem Ziel, PNGs auf Platte
zu schreiben statt Assertions zu prüfen.

Wichtig, in dieser Reihenfolge:

1. `FLUGRADAR_DATA_DIR` MUSS gesetzt sein, bevor irgendetwas aus
   `flugradar.config.settings` importiert wird -- `PORTAL_SETTINGS_FILE`
   ist eine Modulkonstante, die beim Import ausgewertet wird. Das Menü
   schreibt bei jedem Tap sofort in diese Datei (`menu.py:_save`); ohne
   ein eigenes, temporäres Datenverzeichnis würden die Bildläufe hier die
   echten Geräteeinstellungen überschreiben.
2. `pygame.init()`/`pygame.quit()` läuft genau einmal für den gesamten
   Lauf -- `fonts.get_font()` cacht `Font`-Objekte, die nach `pygame.quit()`
   segfaulten statt zu werfen (siehe `flugradar/tests/conftest.py`).
3. `Inter` muss als Systemschrift verfügbar sein (`apt install fonts-inter
   fonts-ibm-plex`), sonst rendert `flugradar/display/fonts.py` still mit
   DejaVu -- ein optisch anderes Ergebnis als das echte Gerät. Wird hier
   hart geprüft statt still zu toleriere.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_DATA_DIR = Path(tempfile.mkdtemp(prefix="srt-anleitung-"))
os.environ["FLUGRADAR_DATA_DIR"] = str(_DATA_DIR)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from flugradar.config.settings import AppSettings  # noqa: E402
from flugradar.data_sources.models import Aircraft  # noqa: E402
from flugradar.data_sources.projection import ScreenProjection  # noqa: E402
from flugradar.display import fonts, scaling  # noqa: E402
from flugradar.display.mask import create_bezel_ring  # noqa: E402
from flugradar.display.renderer import RadarRenderer  # noqa: E402
from flugradar.display.screens import about as about_mod  # noqa: E402
from flugradar.display.screens import menu as menu_mod  # noqa: E402
from flugradar.display.screens.about import AboutScreen  # noqa: E402
from flugradar.display.screens.clock import ClockScreen  # noqa: E402
from flugradar.display.screens.detail import DetailScreen  # noqa: E402
from flugradar.display.screens.menu import MenuScreen  # noqa: E402
from flugradar.display.screens.radar import RadarScreen  # noqa: E402
from flugradar.display.screens.tracking import TrackedFlightScreen  # noqa: E402
from flugradar.display.screens.weather import WeatherScreen  # noqa: E402
from flugradar.display.screens.wifi import WifiScreen  # noqa: E402
from flugradar.display.theme import CLASSIC_AMBER  # noqa: E402
from flugradar.system import network  # noqa: E402

from anleitung import szene  # noqa: E402

SIZE = 720
THEME = CLASSIC_AMBER


def _seed_first_seen(renderer: RadarRenderer, aircraft: list[Aircraft]) -> None:
    """Zeitpunkt 0 statt "jetzt" für jedes Flugzeug vorbelegen.

    `RadarRenderer.draw_aircraft()` blendet neu erschienene Flugzeuge über
    `TOKENS.duration_short_ms` sanft ein (`age = now - first_seen`, Alpha 0
    beim allerersten Frame). Mit eingefrorener Zeit (`szene.frozen_time()`)
    ist `now` bei jedem Aufruf identisch -- ohne dieses Vorbelegen bliebe
    jedes Flugzeug für immer bei Alpha 0, also unsichtbar. Ein Fake-
    `first_seen` von 0.0 lässt `age` sofort riesig erscheinen -> voller
    Alpha gleich beim ersten (und einzigen) Render.
    """
    for ac in aircraft:
        renderer._first_seen[ac.icao_hex] = 0.0


def _patch_identity() -> None:
    """Hostname/IP für Screenshots auf plausible Platzhalter setzen.

    `about._hostname()`/`_ip_address()` lesen echte Systemwerte
    (`socket.gethostname()` etc.) -- in diesem Build-Container wäre das
    z. B. "vm", was im gedruckten Buch wie ein Artefakt der Build-Umgebung
    aussähe statt wie ein echtes Gerät. `menu.py` importiert beide
    Funktionen per `from ... import` (eigene Namensbindung), daher müssen
    beide Module einzeln gepatcht werden.
    """
    def hostname() -> str:
        return "sasso"

    def ip_address() -> str:
        return "192.168.1.42"

    about_mod._hostname = hostname
    about_mod._ip_address = ip_address
    menu_mod._hostname = hostname
    menu_mod._ip_address = ip_address


def _require_inter() -> None:
    pygame.font.init()
    available = {n.lower() for n in pygame.font.get_fonts()}
    if "inter" not in available:
        raise SystemExit(
            "Systemschrift 'Inter' fehlt -- die Screenshots würden dann auf "
            "DejaVu statt Inter zurückfallen und optisch nicht dem echten "
            "Gerät entsprechen. Installieren mit:\n"
            "  sudo apt-get install -y fonts-inter fonts-ibm-plex"
        )


def _float_disc(surface: pygame.Surface, bezel_colour: tuple[int, int, int]) -> pygame.Surface:
    """Löst die Scheibe aus dem 720x720-Quadrat: alles außerhalb des
    Kreises wird transparent statt schwarz, plus der echte Bezelring --
    damit die Radarscheibe im Buch frei auf dem Papier schwebt statt in
    einem schwarzen Kasten zu sitzen.

    Klassischer pygame-Trick für kreisrunde Ausschnitte: eine Maske mit
    einem opaken, weißen Kreis auf transparentem Grund, multipliziert per
    BLEND_RGBA_MULT mit dem Quellbild -- innerhalb des Kreises kommt die
    Originalfarbe unverändert durch (255*x/255=x), außerhalb bleibt es
    (0,0,0,0). Kein Bezug zu `mask.create_circle_mask()`, die stattdessen
    die Ecken schwarz übermalt (richtig fürs echte Gerät, falsch fürs Buch).
    """
    size = surface.get_width()
    punch = pygame.Surface((size, size), pygame.SRCALPHA)
    punch.fill((0, 0, 0, 0))
    pygame.draw.circle(punch, (255, 255, 255, 255), (size // 2, size // 2), size // 2)
    src = surface.convert_alpha()
    punch.blit(src, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    bezel = create_bezel_ring(size, width=4, colour=bezel_colour)
    punch.blit(bezel, (0, 0))
    return punch


class ScreenshotSet:
    """Rendert alle Buch-Screenshots in einem einzigen pygame-Zyklus."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _save(self, surface: pygame.Surface, name: str, *, disc: bool = True) -> Path:
        img = _float_disc(surface, THEME.radar_ring) if disc else surface
        path = self.out_dir / f"{name}.png"
        pygame.image.save(img, str(path))
        return path

    def run(self) -> list[Path]:
        _require_inter()
        _patch_identity()
        pygame.init()
        pygame.display.set_mode((SIZE, SIZE))
        scaling.init(SIZE)
        try:
            with szene.frozen_time():
                paths: list[Path] = []
                paths += self._radar_and_legend()
                paths += self._detail()
                paths += self._tracking()
                paths += self._clock_and_weather()
                paths += self._about()
                paths += self._wifi()
                paths += self._menu()
                return paths
        finally:
            pygame.quit()
            fonts.reset_cache()

    # ---- Radar + Legende ------------------------------------------------

    def _radar_and_legend(self) -> list[Path]:
        proj = ScreenProjection(szene.HOME_LAT, szene.HOME_LON, 100.0, SIZE)
        screen = RadarScreen(SIZE, proj, THEME)
        aircraft = szene.build_aircraft()
        _seed_first_seen(screen.renderer, aircraft)
        surf = pygame.Surface((SIZE, SIZE))
        screen.draw(surf, aircraft, weather_str=szene.build_weather().temperature_str())
        out = [self._save(surf, "radar")]

        # Legende: fünf einzelne Icon-Zustände (normal, ausgewählt,
        # verfolgt, militärisch, Notfall) auf einer kleinen, eigenen
        # Projektion, bei der das Flugzeug exakt in der Mitte sitzt
        # (radius/Distanz spielen dabei keine Rolle -- die Zelle ist nur
        # groß genug fürs Icon selbst).
        legend_size = 140
        legend_proj = ScreenProjection(szene.HOME_LAT, szene.HOME_LON, 10.0, legend_size)
        legend_renderer = RadarRenderer(legend_size, legend_proj, THEME, show_rings=False, show_aircraft_tags=False)
        base = Aircraft(
            icao_hex="legend", lat=szene.HOME_LAT, lon=szene.HOME_LON,
            altitude_ft=10000, ground_speed_kt=200, track_deg=0, distance_km=0, bearing_deg=0,
        )
        variants = {
            "legende-normal": (base, "", ""),
            "legende-ausgewaehlt": (base, "legend", ""),
            "legende-verfolgt": (base, "", "legend"),
        }
        for name, (ac, sel, trk) in variants.items():
            _seed_first_seen(legend_renderer, [ac])
            s = pygame.Surface((legend_size, legend_size), pygame.SRCALPHA)
            s.fill(THEME.background)
            legend_renderer.draw_aircraft(s, [ac], sel, trk)
            out.append(self._save(s, name, disc=False))

        military = Aircraft(
            icao_hex="mil", lat=szene.HOME_LAT, lon=szene.HOME_LON,
            altitude_ft=25000, ground_speed_kt=400, track_deg=0,
            callsign="TOPCAT11", distance_km=0, bearing_deg=0,
        )
        _seed_first_seen(legend_renderer, [military])
        s = pygame.Surface((legend_size, legend_size), pygame.SRCALPHA)
        s.fill(THEME.background)
        legend_renderer.draw_aircraft(s, [military], "", "")
        out.append(self._save(s, "legende-militaer", disc=False))

        emergency = Aircraft(
            icao_hex="emg", lat=szene.HOME_LAT, lon=szene.HOME_LON,
            altitude_ft=8000, ground_speed_kt=250, track_deg=0,
            squawk="7700", distance_km=0, bearing_deg=0,
        )
        _seed_first_seen(legend_renderer, [emergency])
        s = pygame.Surface((legend_size, legend_size), pygame.SRCALPHA)
        s.fill(THEME.background)
        legend_renderer.draw_aircraft(s, [emergency], "", "")
        out.append(self._save(s, "legende-notfall", disc=False))
        return out

    # ---- Flugdetail -------------------------------------------------------

    def _detail(self) -> list[Path]:
        out = []
        flight = szene.build_tracked_flight()
        aircraft = szene.build_aircraft()

        screen = DetailScreen(SIZE, THEME)
        screen.set_aircraft(flight)
        screen.set_aircraft_list([flight, *aircraft])
        surf = pygame.Surface((SIZE, SIZE))
        screen.draw(surf)
        out.append(self._save(surf, "detail"))

        emergency = next(a for a in aircraft if a.is_emergency)
        screen2 = DetailScreen(SIZE, THEME)
        screen2.set_aircraft(emergency)
        screen2.set_aircraft_list(aircraft)
        surf2 = pygame.Surface((SIZE, SIZE))
        screen2.draw(surf2)
        out.append(self._save(surf2, "detail-notfall"))
        return out

    # ---- Verfolgter Flug ----------------------------------------------

    def _tracking(self) -> list[Path]:
        out = []
        flight = szene.build_tracked_flight()

        screen = TrackedFlightScreen(SIZE, THEME)
        screen.set_tracking(flight, True, 0.0)
        surf = pygame.Surface((SIZE, SIZE))
        screen.draw(surf)
        out.append(self._save(surf, "tracking"))

        no_route = Aircraft(
            icao_hex="noroute", callsign="AZA204", aircraft_type="A320",
            lat=szene.HOME_LAT, lon=szene.HOME_LON, altitude_ft=6000,
            ground_speed_kt=180, track_deg=90, origin="NAP", destination="MXP",
        )
        screen2 = TrackedFlightScreen(SIZE, THEME)
        screen2.set_tracking(no_route, True, 0.0)
        surf2 = pygame.Surface((SIZE, SIZE))
        screen2.draw(surf2)
        out.append(self._save(surf2, "tracking-ohne-route"))
        return out

    # ---- Uhr + Wetter ---------------------------------------------------

    def _clock_and_weather(self) -> list[Path]:
        out = []
        clock = ClockScreen(SIZE, THEME)
        weather = szene.build_weather()
        clock.set_weather(weather.temperature_str(), weather.condition)
        surf = pygame.Surface((SIZE, SIZE))
        clock.draw(surf)
        out.append(self._save(surf, "uhr"))

        w = WeatherScreen(SIZE, THEME, location_label=szene.location_label())
        w.set_data(
            has_key=True, current=weather, is_stale=False, age_s=None,
            forecast=szene.build_forecast(),
        )
        surf2 = pygame.Surface((SIZE, SIZE))
        w.draw(surf2)
        out.append(self._save(surf2, "wetter"))

        w2 = WeatherScreen(SIZE, THEME, location_label=szene.location_label())
        w2.set_data(has_key=False, current=None, is_stale=False, age_s=None, forecast=[])
        surf3 = pygame.Surface((SIZE, SIZE))
        w2.draw(surf3)
        out.append(self._save(surf3, "wetter-ohne-schluessel"))
        return out

    # ---- Info -------------------------------------------------------------

    def _about(self) -> list[Path]:
        screen = AboutScreen(SIZE, THEME, openaip_enabled=True, rainviewer_enabled=True)
        surf = pygame.Surface((SIZE, SIZE))
        screen.draw(surf)
        return [self._save(surf, "info")]

    # ---- WLAN ---------------------------------------------------------

    def _wifi(self) -> list[Path]:
        out = []
        networks = [
            network.NetworkInfo(ssid="Casa-Sassofortino", signal=88, secured=True, is_current=True),
            network.NetworkInfo(ssid="TIM-44827193", signal=54, secured=True),
            network.NetworkInfo(ssid="Vodafone-Gast", signal=31, secured=False),
        ]

        screen = WifiScreen(SIZE, THEME)
        screen._networks = networks
        surf = pygame.Surface((SIZE, SIZE))
        screen.draw(surf)
        out.append(self._save(surf, "wlan-liste"))

        screen2 = WifiScreen(SIZE, THEME)
        screen2._networks = networks
        screen2._mode = "password"
        screen2._selected = networks[1]
        surf2 = pygame.Surface((SIZE, SIZE))
        screen2.draw(surf2)
        out.append(self._save(surf2, "wlan-passwort"))
        return out

    # ---- Einstellungen --------------------------------------------------

    @staticmethod
    def _find_row(menu: MenuScreen, surf: pygame.Surface, key: str):
        """Zeile per Schlüssel finden, notfalls bis ans Ende scrollen.

        Gleiches Vorgehen wie `_tap_row()` in `flugradar/tests/test_menu.py`:
        eine lange Liste (z. B. System mit 9 Zeilen) zeigt nicht jede Zeile
        gleichzeitig, `handle_tap` kann also nur treffen, was gerade
        gezeichnet ist.
        """
        menu.draw(surf)
        for rect, row in menu._row_rects:
            if row.key == key:
                return rect, row
        menu._scroll._anim_from = menu._scroll._anim_to = menu._scroll.max_offset
        menu.draw(surf)
        for rect, row in menu._row_rects:
            if row.key == key:
                return rect, row
        raise AssertionError(f"Menüzeile {key!r} nicht gefunden")

    def _menu(self) -> list[Path]:
        out = []
        settings = AppSettings()
        # Standort auf Sassofortino setzen, damit "Standort -> Ort" im
        # Screenshot als ausgewählt (statt Zürich-Default) erscheint.
        settings.home.lat = szene.HOME_LAT
        settings.home.lon = szene.HOME_LON
        settings.home.radius_km = 100.0
        menu = MenuScreen(SIZE, THEME, settings)
        surf = pygame.Surface((SIZE, SIZE))
        menu.draw(surf)
        out.append(self._save(surf, "menu-wurzel"))

        submenus = ("map", "location", "display", "filter", "screen", "units", "system")
        for key in submenus:
            menu._open_submenu(key)
            menu._level_from = None  # Slide-Animation überspringen, siehe Moduldoc
            surf = pygame.Surface((SIZE, SIZE))
            menu.draw(surf)
            out.append(self._save(surf, f"menu-{key}"))
            menu.go_back()
            menu._level_from = None

        # Ein Stufenregler in Aktion (Mindesthöhe im Filter-Untermenü) --
        # ein Tap etwa in der Mitte der Zeile setzt einen mittleren Wert.
        menu._open_submenu("filter")
        menu._level_from = None
        surf = pygame.Surface((SIZE, SIZE))
        rect, _ = self._find_row(menu, surf, "min_alt")
        menu.handle_tap(rect.left + int(rect.width * 0.4), rect.centery)
        surf = pygame.Surface((SIZE, SIZE))
        menu.draw(surf)
        out.append(self._save(surf, "menu-regler"))
        menu.go_back()
        menu._level_from = None

        # Die Bestätigen/Abbrechen-Rückfrage bei "Neustart" -- EIN Tap
        # setzt nur `_confirm_key` (siehe Moduldoc), löst NICHT
        # `system_action("reboot")` aus. Niemals ein zweites Mal tappen.
        menu._open_submenu("system")
        menu._level_from = None
        surf = pygame.Surface((SIZE, SIZE))
        rect, _ = self._find_row(menu, surf, "restart")
        menu.handle_tap(rect.centerx, rect.centery)
        # Nach dem Tap steht `_confirm_key`, aber die Zeile könnte durch den
        # Scroll-zum-Ende-Kniff oberhalb des sichtbaren Bereichs liegen --
        # noch einmal ans Ende scrollen, damit sie im Bild ist.
        menu._scroll._anim_from = menu._scroll._anim_to = menu._scroll.max_offset
        surf = pygame.Surface((SIZE, SIZE))
        menu.draw(surf)
        out.append(self._save(surf, "menu-bestaetigen"))
        return out


def render_all(out_dir: Path) -> list[Path]:
    try:
        return ScreenshotSet(out_dir).run()
    finally:
        shutil.rmtree(_DATA_DIR, ignore_errors=True)


if __name__ == "__main__":
    default_out = Path(__file__).parent / "bilder"
    paths = render_all(default_out)
    print(f"{len(paths)} Bilder geschrieben nach {default_out}")

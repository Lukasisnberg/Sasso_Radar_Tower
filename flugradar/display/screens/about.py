"""About screen — version, network status, portal URL.

Centered layout fitted to the round display with Dieter Rams typography.
"""

import socket
from typing import Optional

import pygame

from flugradar import __version__
from flugradar.display import nav, scaling
from flugradar.display.draw_helpers import draw_center_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import TOKENS, Theme


class AboutScreen:
    """Displays version info, network status, and web portal URL."""

    def __init__(
        self,
        screen_size: int,
        theme: Theme,
        openaip_enabled: bool = False,
        rainviewer_enabled: bool = False,
    ) -> None:
        self.size = screen_size
        self.theme = theme
        self.openaip_enabled = openaip_enabled
        self.rainviewer_enabled = rainviewer_enabled
        self._fonts_ready = False
        self._title_font: Optional[pygame.font.Font] = None
        self._detail_font: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._title_font = get_font(scaling.s(TOKENS.font_title), bold=True)
            self._detail_font = get_font(scaling.s(TOKENS.font_small))
            self._fonts_ready = True

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)

        nav.draw_breadcrumb(surface, ["Radar", "About"], self.theme)

        top = nav.content_top_y()
        bottom = nav.content_bottom_y()
        y = top

        y = draw_center_text(surface, "Sasso Radar Tower", y, self._title_font, self.theme.label)
        y += scaling.s(4)

        lines = [
            f"v{__version__}",
            "",
            f"{_hostname()} · {_ip_address()}",
            f"http://{_hostname()}.local:5000",
            "",
            f"Bildschirm {self.size}×{self.size}",
            "Daten: adsb.fi (opendata)",
            "Anreicherung: adsbdb.com (opendata)",
            "Karten: CARTO / OpenStreetMap",
            "Fotos: planespotters.net",
            "Icons: adsb-radar.com",
            "Wettericons: erikflowers.github.io (SIL OFL 1.1)",
        ]
        if self.openaip_enabled:
            lines.append("Luftraum-Overlay: openAIP.net (CC BY-NC 4.0)")
        if self.rainviewer_enabled:
            lines.append("Regenradar: RainViewer.com")

        for line in lines:
            if not line:
                y += scaling.s(4)
                continue
            if y + self._detail_font.get_height() > bottom:
                break
            y = draw_center_text(surface, line, y, self._detail_font, self.theme.muted)

        nav.draw_footer_buttons(surface, ["radar"], self.theme)

    def handle_tap(self, x: int, y: int) -> bool:
        idx = nav.tap_footer_button(x, y, 1)
        if idx is not None:
            return True
        breadcrumb_y = scaling.center_y() - int(scaling.visible_radius() * 0.75)
        if y < breadcrumb_y + scaling.s(30):
            return True
        return False


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unbekannt"


def _ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        addr = s.getsockname()[0]
        s.close()
        return addr
    except Exception:
        return "kein Netzwerk"

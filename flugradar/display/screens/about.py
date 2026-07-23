"""About screen — version, network status, portal URL."""

import socket
from typing import Optional

import pygame

from flugradar import __version__
from flugradar.display.theme import Theme


class AboutScreen:
    """Displays version info, network status, and web portal URL."""

    def __init__(self, screen_size: int, theme: Theme) -> None:
        self.size = screen_size
        self.theme = theme
        self._font: Optional[pygame.font.Font] = None
        self._font_lg: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        self._back_rect: Optional[pygame.Rect] = None

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 16)
            self._font_lg = pygame.font.SysFont("monospace", 26, bold=True)
            self._font_sm = pygame.font.SysFont("monospace", 13)

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)
        cx = self.size // 2
        y = 60

        title = self._font_lg.render("Sasso Radar Tower", True, self.theme.compass_text)
        surface.blit(title, (cx - title.get_width() // 2, y))
        y += 50

        lines = [
            ("Version", __version__),
            ("Hostname", _hostname()),
            ("IP Address", _ip_address()),
            ("Portal", f"http://{_hostname()}.local:5000"),
            ("Data Source", "adsb.fi (opendata)"),
            ("Display", f"{self.size}x{self.size}"),
        ]

        for label, value in lines:
            lbl = self._font.render(f"{label}:", True, self.theme.range_label)
            val = self._font.render(value, True, self.theme.info_text)
            surface.blit(lbl, (60, y))
            surface.blit(val, (220, y))
            y += 30

        y += 20
        attr = self._font_sm.render(
            "Data: adsb.fi | Maps: CARTO / OSM", True, self.theme.radar_ring
        )
        surface.blit(attr, (cx - attr.get_width() // 2, y))

        y = self.size - 50
        back = self._font.render("[ BACK ]", True, self.theme.compass_text)
        bx = cx - back.get_width() // 2
        surface.blit(back, (bx, y))
        self._back_rect = pygame.Rect(bx - 10, y - 5, back.get_width() + 20, back.get_height() + 10)

    def handle_tap(self, x: int, y: int) -> bool:
        if self._back_rect and self._back_rect.collidepoint(x, y):
            return True
        return False


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def _ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        addr = s.getsockname()[0]
        s.close()
        return addr
    except Exception:
        return "no network"

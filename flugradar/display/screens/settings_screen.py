"""On-device settings screen — brightness, theme, display options."""

from typing import Optional

import pygame

from flugradar.display.theme import Theme, THEMES


class SettingsScreen:
    """Touch-friendly settings panel for display options."""

    def __init__(self, screen_size: int, theme: Theme) -> None:
        self.size = screen_size
        self.theme = theme
        self._font: Optional[pygame.font.Font] = None
        self._font_lg: Optional[pygame.font.Font] = None
        self._back_rect: Optional[pygame.Rect] = None
        self._items: list[tuple[str, list[str], int]] = [
            ("Theme", list(THEMES.keys()), 0),
            ("Unit", ["km", "sm", "nm"], 0),
        ]
        self._item_rects: list[list[pygame.Rect]] = []

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 18)
            self._font_lg = pygame.font.SysFont("monospace", 24, bold=True)

    @property
    def selected_theme(self) -> str:
        _, options, idx = self._items[0]
        return options[idx]

    @property
    def selected_unit(self) -> str:
        _, options, idx = self._items[1]
        return options[idx]

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)
        cx = self.size // 2
        y = 60

        title = self._font_lg.render("Settings", True, self.theme.compass_text)
        surface.blit(title, (cx - title.get_width() // 2, y))
        y += 60

        self._item_rects = []
        for label, options, selected_idx in self._items:
            lbl = self._font.render(f"{label}:", True, self.theme.range_label)
            surface.blit(lbl, (40, y))

            option_rects = []
            ox = 200
            for i, opt in enumerate(options):
                is_sel = i == selected_idx
                colour = self.theme.compass_text if is_sel else self.theme.radar_ring
                text = f"[{opt}]" if is_sel else f" {opt} "
                opt_surf = self._font.render(text, True, colour)
                rect = pygame.Rect(ox, y - 2, opt_surf.get_width() + 8, opt_surf.get_height() + 4)
                surface.blit(opt_surf, (ox + 4, y))
                option_rects.append(rect)
                ox += rect.width + 12
            self._item_rects.append(option_rects)
            y += 50

        y = self.size - 50
        back = self._font.render("[ BACK ]", True, self.theme.compass_text)
        bx = cx - back.get_width() // 2
        surface.blit(back, (bx, y))
        self._back_rect = pygame.Rect(bx - 10, y - 5, back.get_width() + 20, back.get_height() + 10)

    def handle_tap(self, x: int, y: int) -> Optional[str]:
        """Returns 'back' if back tapped, 'changed' if a setting changed, else None."""
        if self._back_rect and self._back_rect.collidepoint(x, y):
            return "back"

        for row_idx, rects in enumerate(self._item_rects):
            for opt_idx, rect in enumerate(rects):
                if rect.collidepoint(x, y):
                    label, options, _ = self._items[row_idx]
                    self._items[row_idx] = (label, options, opt_idx)
                    return "changed"
        return None

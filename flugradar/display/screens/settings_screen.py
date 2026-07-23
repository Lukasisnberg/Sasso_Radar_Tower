"""On-device settings screen — theme and unit selection.

Vertical card layout fitted to the round display with Dieter Rams typography.
"""

from typing import Optional

import pygame

from flugradar.display import nav, scaling
from flugradar.display.draw_helpers import draw_center_text, fit_text
from flugradar.display.fonts import get_font
from flugradar.display.theme import Theme, THEMES


class SettingsScreen:
    """Touch-friendly settings panel for display options."""

    def __init__(self, screen_size: int, theme: Theme) -> None:
        self.size = screen_size
        self.theme = theme
        self._fonts_ready = False
        self._font_label: Optional[pygame.font.Font] = None
        self._font_option: Optional[pygame.font.Font] = None
        self._theme_keys = list(THEMES.keys())
        self._unit_options = ["km", "sm", "nm"]
        self._selected_theme_idx = 0
        self._selected_unit_idx = 0
        self._option_rects: list[pygame.Rect] = []
        self._option_map: list[tuple[str, int]] = []

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._font_label = get_font(scaling.s(9), bold=True)
            self._font_option = get_font(scaling.s(8))
            self._fonts_ready = True

    @property
    def selected_theme(self) -> str:
        return self._theme_keys[self._selected_theme_idx]

    @property
    def selected_unit(self) -> str:
        return self._unit_options[self._selected_unit_idx]

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(self.theme.background)

        nav.draw_breadcrumb(surface, ["Radar", "Settings"], self.theme)

        top = nav.content_top_y()
        bottom = nav.content_bottom_y()
        cx = scaling.center_x()
        y = top

        self._option_rects.clear()
        self._option_map.clear()

        y = draw_center_text(surface, "Theme", y, self._font_label, self.theme.label)
        y += scaling.s(2)
        y = self._draw_option_group(
            surface, self._theme_keys, self._selected_theme_idx,
            "theme", y, bottom,
        )

        y += scaling.s(8)
        y = draw_center_text(surface, "Unit", y, self._font_label, self.theme.label)
        y += scaling.s(2)
        y = self._draw_option_group(
            surface, self._unit_options, self._selected_unit_idx,
            "unit", y, bottom,
        )

        nav.draw_footer_buttons(surface, ["radar"], self.theme)

    def _draw_option_group(
        self,
        surface: pygame.Surface,
        options: list[str],
        selected_idx: int,
        group: str,
        y: int,
        max_y: int,
    ) -> int:
        cx = scaling.center_x()
        row_h = scaling.s(18)
        pad_x = scaling.s(8)
        pad_y = scaling.s(2)
        gap = scaling.s(3)
        corner = max(2, scaling.s(4))

        for i, opt in enumerate(options):
            if y + row_h > max_y:
                break
            is_sel = i == selected_idx
            hw = scaling.circle_half_width_at_row(y, row_h)
            max_w = hw * 2
            btn_w = min(max_w, scaling.s(90))
            btn_x = cx - btn_w // 2
            rect = pygame.Rect(btn_x, y, btn_w, row_h)

            if is_sel:
                pygame.draw.rect(surface, self.theme.sweep_colour, rect, border_radius=corner)
                text_color = self.theme.background
            else:
                pygame.draw.rect(surface, self.theme.radar_ring, rect, width=1, border_radius=corner)
                text_color = self.theme.muted

            label = fit_text(opt.replace("_", " ").title(), self._font_option, btn_w - pad_x * 2)
            rendered = self._font_option.render(label, True, text_color)
            surface.blit(rendered, rendered.get_rect(center=rect.center))

            self._option_rects.append(rect)
            self._option_map.append((group, i))
            y += row_h + gap

        return y

    def handle_tap(self, x: int, y: int) -> Optional[str]:
        """Returns 'back' if back tapped, 'changed' if a setting changed, else None."""
        idx = nav.tap_footer_button(x, y, 1)
        if idx is not None:
            return "back"

        for rect, (group, opt_idx) in zip(self._option_rects, self._option_map):
            if rect.collidepoint(x, y):
                if group == "theme":
                    if opt_idx != self._selected_theme_idx:
                        self._selected_theme_idx = opt_idx
                        return "changed"
                elif group == "unit":
                    if opt_idx != self._selected_unit_idx:
                        self._selected_unit_idx = opt_idx
                        return "changed"
                return None
        return None

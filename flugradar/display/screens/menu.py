"""On-device settings menu (Ausbaustufe 2, Schritt 4 -- docs/prompt-ausbaustufe-2.md).

Two levels, no third: a root list (Karte/Standort/Darstellung/Filter/
Anzeige/Einheiten/System) and one submenu each. Opened via swipe-left from
the radar, closed via swipe-right or the top-left back arrow -- both pop
one level, or return to the radar if already at the root.

Every row is one of four widget kinds (Umschalter/Einfachauswahl/
Stufenregler/Aktion-mit-Rückfrage per 4.3) plus a read-only "info" kind for
the System submenu. Rows are declarative (`_Row`) so the shared layout/
hit-testing code doesn't have to special-case each of the ~20 settings.
Every change is written immediately via `settings.save_portal_settings()`
-- no save button, per 4.5.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Optional

import pygame

from flugradar import __version__
from flugradar.config.locations import LOCATIONS, RADIUS_PRESETS_KM, current_location_key
from flugradar.config.settings import AppSettings
from flugradar.data_sources.geo import km_to_unit, unit_label
from flugradar.display import nav, scaling
from flugradar.display.draw_helpers import fit_text
from flugradar.display.fonts import get_font
from flugradar.display.screens.about import _hostname, _ip_address
from flugradar.display.theme import TOKENS, Theme, ease_out_cubic
from flugradar.system.actions import system_action
from flugradar.system.update import trigger_update_async

_SLIDE_DURATION_S = TOKENS.duration_long_ms / 1000.0


@dataclass
class _Row:
    key: str
    label: str
    kind: str  # toggle | select | slider | action | trigger | info | nav
    get_bool: Optional[Callable[[], bool]] = None
    set_bool: Optional[Callable[[bool], dict]] = None
    options: Optional[list[tuple[str, str]]] = None  # (value, display)
    get_value: Optional[Callable[[], str]] = None
    set_value: Optional[Callable[[str], dict]] = None
    min_v: int = 0
    max_v: int = 100
    step_v: int = 1
    get_int: Optional[Callable[[], int]] = None
    set_int: Optional[Callable[[int], dict]] = None
    format_int: Optional[Callable[[int], str]] = None
    run: Optional[Callable[[], None]] = None
    get_text: Optional[Callable[[], str]] = None
    enabled: Callable[[], bool] = lambda: True
    submenu_key: Optional[str] = None


_ROOT_ORDER = ("map", "location", "display", "filter", "screen", "units", "system")
_ROOT_LABELS = {
    "map": "Karte",
    "location": "Standort",
    "display": "Darstellung",
    "filter": "Filter",
    "screen": "Anzeige",
    "units": "Einheiten",
    "system": "System",
}

_AUTO_CLOCK_PRESETS = (
    ("0", "Aus"), ("60", "1 min"), ("300", "5 min"), ("600", "10 min"), ("1800", "30 min"),
)
_HALF_HOURS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]


class MenuScreen:
    """Round-panel two-level settings menu, backed directly by AppSettings."""

    def __init__(self, screen_size: int, theme: Theme, settings: AppSettings) -> None:
        self.size = screen_size
        self.theme = theme
        self.settings = settings
        self._open: Optional[str] = None  # None == root list
        self._scroll = nav.ScrollState()
        self._confirm_key: Optional[str] = None
        self._row_rects: list[tuple[pygame.Rect, _Row]] = []
        self._back_rect = pygame.Rect(0, 0, 0, 0)

        self._level_from: Optional[pygame.Surface] = None
        self._level_start = 0.0
        self._prev_level_surface: Optional[pygame.Surface] = None

        self._fonts_ready = False
        self._font_title: Optional[pygame.font.Font] = None
        self._font_label: Optional[pygame.font.Font] = None
        self._font_value: Optional[pygame.font.Font] = None
        self._font_small: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if not self._fonts_ready:
            self._font_title = get_font(scaling.s(TOKENS.font_title), bold=True)
            self._font_label = get_font(scaling.s(TOKENS.font_standard))
            self._font_value = get_font(scaling.s(TOKENS.font_standard), mono=True)
            self._font_small = get_font(scaling.s(TOKENS.font_small))
            self._fonts_ready = True

    # ---- row definitions ----------------------------------------------

    def _save(self, updates: dict) -> None:
        self.settings.save_portal_settings(updates)

    def _rows_for(self, key: str) -> list[_Row]:
        s = self.settings
        if key == "map":
            return [
                _Row(
                    "map_provider", "Anbieter", "select",
                    options=[
                        ("carto_dark", "CARTO dunkel"), ("carto_light", "CARTO hell"),
                        ("osm", "OpenStreetMap"), ("none", "Keine Karte"),
                    ],
                    get_value=lambda: s.map_provider,
                    set_value=lambda v: {"map_provider": v},
                ),
                _Row(
                    "openaip", "openAIP-Luftraum", "toggle",
                    get_bool=lambda: s.openaip_overlay_enabled,
                    set_bool=lambda v: {"openaip_overlay_enabled": v},
                    enabled=lambda: bool(s.openaip_api_key),
                ),
                _Row(
                    "rainviewer", "Regenradar", "toggle",
                    get_bool=lambda: s.rainviewer_enabled,
                    set_bool=lambda v: {"rainviewer_enabled": v},
                ),
                _Row(
                    "map_brightness", "Kartenhelligkeit", "slider",
                    min_v=0, max_v=100, step_v=5,
                    get_int=lambda: s.map_brightness,
                    set_int=lambda v: {"map_brightness": v},
                    format_int=lambda v: f"{v}%",
                ),
            ]
        if key == "location":
            rows = [
                _Row(
                    "home_location", "Ort", "select",
                    options=[(l.key, l.label) for l in LOCATIONS],
                    get_value=lambda: current_location_key(s.home.lat, s.home.lon) or "",
                    set_value=self._set_location,
                ),
                _Row(
                    "radius", "Radius", "select",
                    options=[
                        (str(km), f"{km_to_unit(km, s.distance_unit):.0f} {unit_label(s.distance_unit)}")
                        for km in RADIUS_PRESETS_KM
                    ],
                    get_value=lambda: str(_nearest(RADIUS_PRESETS_KM, s.home.radius_km)),
                    set_value=lambda v: {"radius_km": float(v)},
                ),
            ]
            return rows
        if key == "display":
            return [
                _Row(
                    "theme", "Theme", "select",
                    options=[("amber", "Amber"), ("mono", "Mono")],
                    get_value=lambda: s.theme,
                    set_value=lambda v: {"theme": v},
                ),
                _Row(
                    "icon_set", "Icon-Set", "select",
                    options=[("detailed", "Detailliert"), ("simple", "Einfach")],
                    get_value=lambda: s.aircraft_icon_set,
                    set_value=lambda v: {"aircraft_icon_set": v},
                ),
                _Row(
                    "tags", "Beschriftung", "toggle",
                    get_bool=lambda: s.show_aircraft_tags,
                    set_bool=lambda v: {"show_aircraft_tags": v},
                ),
                _Row(
                    "compass", "Kompassrose", "toggle",
                    get_bool=lambda: s.show_compass,
                    set_bool=lambda v: {"show_compass": v},
                ),
                _Row(
                    "sweep", "Sweep", "toggle",
                    get_bool=lambda: s.show_sweep,
                    set_bool=lambda v: {"show_sweep": v},
                ),
                _Row(
                    "rings", "Ringe", "toggle",
                    get_bool=lambda: s.show_rings,
                    set_bool=lambda v: {"show_rings": v},
                ),
            ]
        if key == "filter":
            return [
                _Row(
                    "min_alt", "Mindesthöhe", "slider",
                    min_v=0, max_v=10000, step_v=250,
                    get_int=lambda: s.min_altitude_ft,
                    set_int=lambda v: {"min_altitude_ft": v},
                    format_int=lambda v: f"{v} ft",
                ),
                _Row(
                    "hl_emergency", "Notfall hervorheben", "toggle",
                    get_bool=lambda: s.highlight_emergency,
                    set_bool=lambda v: {"highlight_emergency": v},
                ),
                _Row(
                    "hl_military", "Militär hervorheben", "toggle",
                    get_bool=lambda: s.highlight_military,
                    set_bool=lambda v: {"highlight_military": v},
                ),
                _Row(
                    "only_hl", "Nur Hervorgehobene", "toggle",
                    get_bool=lambda: s.only_highlighted,
                    set_bool=lambda v: {"only_highlighted": v},
                ),
            ]
        if key == "screen":
            rows = [
                _Row(
                    "brightness", "Helligkeit", "slider",
                    min_v=10, max_v=100, step_v=5,
                    get_int=lambda: s.brightness,
                    set_int=lambda v: {"brightness": v},
                    format_int=lambda v: f"{v}%",
                ),
                _Row(
                    "night_mode", "Nachtmodus", "toggle",
                    get_bool=lambda: s.night_mode_enabled,
                    set_bool=lambda v: {"night_mode_enabled": v},
                ),
            ]
            if s.night_mode_enabled:
                rows += [
                    _Row(
                        "night_start", "Nachtmodus ab", "select",
                        options=[(t, t) for t in _HALF_HOURS],
                        get_value=lambda: s.night_mode_start,
                        set_value=lambda v: {"night_mode_start": v},
                    ),
                    _Row(
                        "night_end", "Nachtmodus bis", "select",
                        options=[(t, t) for t in _HALF_HOURS],
                        get_value=lambda: s.night_mode_end,
                        set_value=lambda v: {"night_mode_end": v},
                    ),
                    _Row(
                        "night_brightness", "Nachthelligkeit", "slider",
                        min_v=5, max_v=100, step_v=5,
                        get_int=lambda: s.night_mode_brightness,
                        set_int=lambda v: {"night_mode_brightness": v},
                        format_int=lambda v: f"{v}%",
                    ),
                ]
            rows.append(
                _Row(
                    "auto_clock", "Automatisch zur Uhr", "select",
                    options=list(_AUTO_CLOCK_PRESETS),
                    get_value=lambda: str(_nearest_str(_AUTO_CLOCK_PRESETS, s.auto_clock_s)),
                    set_value=lambda v: {"auto_clock_s": int(v)},
                )
            )
            return rows
        if key == "units":
            return [
                _Row(
                    "distance_unit", "Distanz", "select",
                    options=[("km", "km"), ("sm", "sm"), ("nm", "nm")],
                    get_value=lambda: s.distance_unit,
                    set_value=lambda v: {"distance_unit": v},
                ),
                _Row(
                    "temperature_unit", "Temperatur", "select",
                    options=[("c", "°C"), ("f", "°F")],
                    get_value=lambda: s.temperature_unit,
                    set_value=lambda v: {"temperature_unit": v},
                ),
                _Row(
                    "time_format", "Uhrzeit", "select",
                    options=[("24h", "24 h"), ("12h", "12 h")],
                    get_value=lambda: s.time_format,
                    set_value=lambda v: {"time_format": v},
                ),
            ]
        if key == "system":
            return [
                _Row("version", "Version", "info", get_text=lambda: f"v{__version__}"),
                _Row("hostname", "Hostname", "info", get_text=_hostname),
                _Row("ip", "IP-Adresse", "info", get_text=_ip_address),
                _Row("portal", "Portal", "info", get_text=lambda: f"{_hostname()}.local:5000"),
                _Row("sources", "Datenquellen", "info", get_text=lambda: "adsb.fi, adsbdb.com"),
                _Row("update", "Update", "action", run=trigger_update_async),
                _Row("wifi_setup", "WLAN einrichten", "trigger"),
                _Row("restart", "Neustart", "action", run=lambda: system_action("reboot")),
                _Row("shutdown", "Herunterfahren", "action", run=lambda: system_action("shutdown")),
            ]
        return []

    def _root_rows(self) -> list[_Row]:
        return [
            _Row(key, _ROOT_LABELS[key], "nav", submenu_key=key)
            for key in _ROOT_ORDER
        ]

    def _set_location(self, key: str) -> dict:
        for loc in LOCATIONS:
            if loc.key == key:
                return {"home_lat": loc.lat, "home_lon": loc.lon}
        return {}

    # ---- navigation -----------------------------------------------------

    def go_back(self) -> str:
        """Pop one level. Returns 'radar' if that means leaving the menu
        entirely (already at root), else 'menu' (stay on this screen)."""
        self._confirm_key = None
        if self._open is not None:
            self._start_slide()
            self._open = None
            self._scroll.reset()
            return "menu"
        return "radar"

    def _open_submenu(self, key: str) -> None:
        self._confirm_key = None
        self._start_slide()
        self._open = key
        self._scroll.reset()

    def _start_slide(self) -> None:
        self._level_start = time.monotonic()
        self._level_from = self._prev_level_surface

    def handle_scroll(self, direction: int) -> None:
        self._scroll.kick(direction * scaling.s(60))

    # ---- rendering --------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        target = pygame.Surface((self.size, self.size))
        self._draw_level(target)

        elapsed = time.monotonic() - self._level_start
        if self._level_from is not None and elapsed < _SLIDE_DURATION_S:
            t = ease_out_cubic(elapsed / _SLIDE_DURATION_S)
            # Opening a submenu slides new content in from the right and
            # pushes the old content out to the left; going back reverses it.
            direction = 1 if self._open is not None else -1
            shift = int(self.size * (1.0 - t)) * direction
            surface.fill(self.theme.background)
            surface.blit(self._level_from, (-self.size * direction + shift, 0))
            surface.blit(target, (shift, 0))
        else:
            self._level_from = None
            surface.blit(target, (0, 0))

        self._prev_level_surface = target

    def _draw_level(self, surface: pygame.Surface) -> None:
        surface.fill(self.theme.background)
        title = _ROOT_LABELS.get(self._open, "Einstellungen") if self._open else "Einstellungen"
        self._draw_header(surface, title)

        rows = self._rows_for(self._open) if self._open else self._root_rows()
        top = nav.content_top_y()
        bottom = nav.content_bottom_y()

        self._row_rects = []
        row_h = scaling.s(35)
        gap = scaling.s(1)
        y = top - self._scroll.current_offset()
        total_h = 0

        for row in rows:
            if top - row_h <= y <= bottom:
                self._draw_row(surface, row, y, row_h)
            if y + row_h >= top and y <= bottom:
                hw = scaling.circle_half_width_at_row(max(y, top), row_h)
                rect = pygame.Rect(scaling.center_x() - hw, y, hw * 2, row_h)
                self._row_rects.append((rect, row))
            y += row_h + gap
            total_h += row_h + gap

        self._scroll.max_offset = max(0, total_h - (bottom - top))
        self._draw_scroll_arc(surface, top, bottom)

    def _draw_header(self, surface: pygame.Surface, title: str) -> None:
        top_y = scaling.center_y() - int(scaling.visible_radius() * 0.75)
        cx = scaling.center_x()

        arrow_size = scaling.s(9)
        arrow_cx = scaling.center_x() - int(scaling.visible_radius() * 0.55)
        arrow_cy = top_y + arrow_size
        pts = [
            (arrow_cx + arrow_size, arrow_cy - arrow_size),
            (arrow_cx - arrow_size, arrow_cy),
            (arrow_cx + arrow_size, arrow_cy + arrow_size),
        ]
        pygame.draw.polygon(surface, self.theme.hint, pts)
        pad = scaling.s(10)
        self._back_rect = pygame.Rect(
            arrow_cx - arrow_size - pad, arrow_cy - arrow_size - pad,
            arrow_size * 2 + pad * 2, arrow_size * 2 + pad * 2,
        )

        title_surf = self._font_title.render(title.upper(), True, self.theme.label)
        surface.blit(title_surf, title_surf.get_rect(midtop=(cx, top_y)))

    def _draw_row(self, surface: pygame.Surface, row: _Row, y: int, row_h: int) -> None:
        hw = scaling.circle_half_width_at_row(y, row_h)
        left = scaling.center_x() - hw
        right = scaling.center_x() + hw
        pad = scaling.s(10)
        enabled = row.enabled()
        label_color = self.theme.label if enabled else self.theme.hint
        value_color = self.theme.sweep_colour if enabled else self.theme.hint

        if row.kind == "action" and self._confirm_key == row.key:
            mid = (left + right) // 2
            confirm_r = pygame.Rect(left + pad, y + scaling.s(4), mid - left - pad - scaling.s(2), row_h - scaling.s(8))
            cancel_r = pygame.Rect(mid + scaling.s(2), y + scaling.s(4), right - mid - pad - scaling.s(2), row_h - scaling.s(8))
            pygame.draw.rect(surface, self.theme.surface_accent, confirm_r, border_radius=scaling.s(6))
            pygame.draw.rect(surface, self.theme.surface, cancel_r, border_radius=scaling.s(6))
            self._blit_centered(surface, "Bestätigen", confirm_r.center, self._font_label, self.theme.sweep_colour)
            self._blit_centered(surface, "Abbrechen", cancel_r.center, self._font_label, self.theme.muted)
            return

        label_surf = self._font_label.render(row.label, True, label_color)
        surface.blit(label_surf, (left + pad, y + (row_h - label_surf.get_height()) // 2))

        if row.kind == "toggle":
            value = "An" if row.get_bool() else "Aus"
        elif row.kind == "select":
            value = dict(row.options).get(row.get_value(), row.get_value())
        elif row.kind == "slider":
            value = row.format_int(row.get_int())
        elif row.kind == "info":
            value = row.get_text()
        elif row.kind == "action":
            value = ""
        else:  # nav / trigger
            value = "›"

        max_val_w = right - pad - (left + pad + label_surf.get_width() + scaling.s(6))
        value_text = fit_text(value, self._font_value, max(0, max_val_w))
        value_surf = self._font_value.render(value_text, True, value_color)
        surface.blit(value_surf, (right - pad - value_surf.get_width(), y + (row_h - value_surf.get_height()) // 2))

        if row.kind == "slider":
            self._draw_slider_track(surface, row, left + pad, right - pad, y + row_h - scaling.s(6), enabled)

        self._draw_divider(surface, left, right, y + row_h)

    def _draw_slider_track(self, surface, row: _Row, x0: int, x1: int, y: int, enabled: bool) -> None:
        frac = 0.0
        if row.max_v > row.min_v:
            frac = (row.get_int() - row.min_v) / (row.max_v - row.min_v)
        frac = max(0.0, min(1.0, frac))
        track_h = max(2, scaling.s(2))
        pygame.draw.line(surface, self.theme.radar_ring, (x0, y), (x1, y), track_h)
        fill_x = x0 + int((x1 - x0) * frac)
        colour = self.theme.sweep_colour if enabled else self.theme.hint
        pygame.draw.line(surface, colour, (x0, y), (fill_x, y), track_h)

    def _draw_divider(self, surface, left: int, right: int, y: int) -> None:
        overlay = pygame.Surface((right - left, 1), pygame.SRCALPHA)
        overlay.fill((*self.theme.radar_ring, TOKENS.hairline_alpha))
        surface.blit(overlay, (left, y))

    def _blit_centered(self, surface, text, center, font, color) -> None:
        surf = font.render(text, True, color)
        surface.blit(surf, surf.get_rect(center=center))

    def _draw_scroll_arc(self, surface: pygame.Surface, top: int, bottom: int) -> None:
        if self._scroll.max_offset <= 0:
            return
        cx, cy = scaling.center_x(), scaling.center_y()
        r = scaling.visible_radius() - scaling.s(4)
        span = bottom - top
        visible_frac = min(1.0, span / (span + self._scroll.max_offset))
        total_arc = math.radians(40)
        arc_len = max(math.radians(4), total_arc * visible_frac)
        progress = self._scroll.current_offset() / self._scroll.max_offset
        start = math.radians(-20) + (total_arc - arc_len) * progress
        rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        pygame.draw.arc(
            surface, self.theme.hint, rect, -(start + arc_len), -start,
            max(1, scaling.s(2)),
        )

    # ---- input --------------------------------------------------------

    def handle_tap(self, x: int, y: int) -> str:
        if self._back_rect.collidepoint(x, y):
            return "menu" if self.go_back() == "menu" else "radar"

        for rect, row in self._row_rects:
            if not rect.collidepoint(x, y):
                continue
            if not row.enabled():
                return ""
            return self._activate(row, x, rect)
        return ""

    def _activate(self, row: _Row, tap_x: int, rect: pygame.Rect) -> str:
        if row.kind == "nav":
            self._open_submenu(row.submenu_key)
            return "menu"
        if row.kind == "toggle":
            self._save(row.set_bool(not row.get_bool()))
            return "changed"
        if row.kind == "select":
            values = [v for v, _ in row.options]
            cur = row.get_value()
            idx = values.index(cur) if cur in values else -1
            nxt = values[(idx + 1) % len(values)]
            self._save(row.set_value(nxt))
            return "changed"
        if row.kind == "slider":
            frac = (tap_x - rect.left) / max(1, rect.width)
            frac = max(0.0, min(1.0, frac))
            raw = row.min_v + frac * (row.max_v - row.min_v)
            stepped = round(raw / row.step_v) * row.step_v
            stepped = max(row.min_v, min(row.max_v, int(stepped)))
            self._save(row.set_int(stepped))
            return "changed"
        if row.kind == "action":
            if self._confirm_key == row.key:
                self._confirm_key = None
                if tap_x < (rect.left + rect.right) // 2:
                    row.run()
                return ""
            self._confirm_key = row.key
            return ""
        if row.kind == "trigger":
            # Single tap, no confirm dance -- unlike "action" (Neustart/
            # Update/...), this has no destructive side effect by itself
            # (it just opens a screen), so the extra Bestätigen/Abbrechen
            # step would only be friction. The caller (RadarApp) reacts to
            # the returned row key to switch screens.
            if row.run:
                row.run()
            return row.key
        return ""


def _nearest(options: tuple[float, ...], value: float) -> float:
    return min(options, key=lambda o: abs(o - value))


def _nearest_str(options: tuple[tuple[str, str], ...], value: int) -> str:
    return min(options, key=lambda o: abs(int(o[0]) - value))[0]

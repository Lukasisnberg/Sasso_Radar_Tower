"""Weather-condition icons: licensed SVG set, resolved from Tomorrow.io
weather codes.

Icon artwork is "Weather Icons" by Erik Flowers (SIL OFL 1.1), vendored
under flugradar/assets/icons/weather/ -- see LICENSE.txt there for the
full license text and source attribution. Icons are recoloured and
cached lazily per (icon key, size, colour), the same pattern used for
the licensed aircraft icon set (flugradar/display/aircraft_icons.py), so
no rasterisation happens per frame.
"""

import logging
import os
from typing import Optional

import pygame

_ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "weather")

# "N/A" glyph from the same set -- a generic "unknown condition" icon,
# used both for weather_code values this table doesn't recognise and as
# the load-failure fallback (see _get_rendered_icon).
GENERIC_ICON = "na"

# Tomorrow.io weather code -> (day icon key, night icon key). Every code
# flugradar.data_sources.weather._WEATHER_CODES can return has an entry
# here. Where erikflowers/weather-icons has no exact match for a code's
# intensity (e.g. no separate "light snow" vs "snow" glyph), the nearest
# available icon is reused rather than falling back to the generic one --
# only genuinely unrecognised codes fall through to GENERIC_ICON via
# resolve_icon()'s .get() default.
_CODE_TO_ICON: dict[int, tuple[str, str]] = {
    1000: ("day-sunny", "night-clear"),  # Clear
    1100: ("day-sunny-overcast", "night-alt-partly-cloudy"),  # Mostly Clear
    1101: ("day-cloudy", "night-alt-cloudy"),  # Partly Cloudy
    1102: ("day-cloudy-high", "night-alt-cloudy-high"),  # Mostly Cloudy
    1001: ("cloudy", "night-cloudy"),  # Cloudy
    2000: ("day-fog", "night-fog"),  # Fog
    2100: ("day-fog", "night-fog"),  # Light Fog -- no lighter variant available
    4000: ("day-sprinkle", "night-alt-sprinkle"),  # Drizzle
    4001: ("day-rain", "night-alt-rain"),  # Rain
    4200: ("day-showers", "night-alt-showers"),  # Light Rain
    4201: ("day-rain-wind", "night-alt-rain-wind"),  # Heavy Rain
    5000: ("day-snow", "night-alt-snow"),  # Snow
    5001: ("day-snow-wind", "night-alt-snow-wind"),  # Flurries
    5100: ("day-snow", "night-alt-snow"),  # Light Snow -- no lighter variant available
    5101: ("day-snow-wind", "night-alt-snow-wind"),  # Heavy Snow
    6000: ("day-rain-mix", "night-alt-rain-mix"),  # Freezing Drizzle
    6001: ("day-sleet", "night-alt-sleet"),  # Freezing Rain
    6200: ("day-rain-mix", "night-alt-rain-mix"),  # Light Freezing Rain
    6201: ("day-sleet-storm", "night-alt-sleet-storm"),  # Heavy Freezing Rain
    7000: ("day-hail", "night-alt-hail"),  # Ice Pellets
    7101: ("day-hail", "night-alt-hail"),  # Heavy Ice Pellets -- no heavier variant available
    7102: ("day-hail", "night-alt-hail"),  # Light Ice Pellets -- no lighter variant available
    8000: ("day-thunderstorm", "night-alt-thunderstorm"),  # Thunderstorm
}


def resolve_icon(weather_code: Optional[int], is_night: bool = False) -> str:
    day_key, night_key = _CODE_TO_ICON.get(weather_code, (GENERIC_ICON, GENERIC_ICON))
    return night_key if is_night else day_key


# icon_key -> loaded raw Surface, or None if the file was missing/corrupt
# (loaded at most once per key, never per frame).
_raw_surface_cache: dict[str, Optional[pygame.Surface]] = {}
# (icon_key, size_px, colour) -> final tinted+scaled Surface (built at
# most once per unique combination, never per frame).
_render_cache: dict[tuple[str, int, tuple[int, int, int]], pygame.Surface] = {}
_warned_missing: set[str] = set()


def _load_raw_icon(icon_key: str) -> Optional[pygame.Surface]:
    if icon_key in _raw_surface_cache:
        return _raw_surface_cache[icon_key]
    path = os.path.join(_ICON_DIR, f"{icon_key}.svg")
    try:
        surface = pygame.image.load(path)
    except (pygame.error, FileNotFoundError, OSError) as exc:
        if icon_key not in _warned_missing:
            _warned_missing.add(icon_key)
            logging.getLogger(__name__).warning(
                "weather icon %r failed to load (%s); falling back to generic icon",
                icon_key, exc,
            )
        surface = None
    _raw_surface_cache[icon_key] = surface
    return surface


def _tint_surface(surface: pygame.Surface, color: tuple[int, int, int]) -> pygame.Surface:
    """Recolour a single-colour silhouette to `color`, preserving alpha --
    same recipe as aircraft_icons.py's _tint_surface()."""
    tinted = surface.copy()
    tinted.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    tinted.fill((*color, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return tinted


def _get_rendered_icon(
    icon_key: str, size_px: int, color: tuple[int, int, int],
) -> Optional[pygame.Surface]:
    cache_key = (icon_key, size_px, color)
    cached = _render_cache.get(cache_key)
    if cached is not None:
        return cached

    raw = _load_raw_icon(icon_key)
    if raw is None:
        if icon_key != GENERIC_ICON:
            return _get_rendered_icon(GENERIC_ICON, size_px, color)
        return None

    scaled = pygame.transform.smoothscale(raw, (size_px, size_px))
    tinted = _tint_surface(scaled, color)
    _render_cache[cache_key] = tinted
    return tinted


def draw_weather_icon(
    surface: pygame.Surface,
    weather_code: Optional[int],
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    is_night: bool = False,
) -> None:
    """Draws the icon for `weather_code` (day or night variant) centred
    at `center`, scaled to fit a `2*radius` square."""
    icon_key = resolve_icon(weather_code, is_night)
    size_px = max(2, radius * 2)
    rendered = _get_rendered_icon(icon_key, size_px, color)
    if rendered is None:
        return
    surface.blit(rendered, rendered.get_rect(center=center))

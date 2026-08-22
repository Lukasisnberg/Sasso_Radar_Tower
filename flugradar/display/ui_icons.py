"""Loader for the licensed Lucide UI-icon set (Schritt 1 of the UI overhaul).

Lucide SVGs use `stroke="currentColor"` and `fill="none"` -- a CSS colour
keyword the SDL_image/nanosvg rasteriser behind `pygame.image.load()` does
not understand (it is a CSS concept, not part of the SVG spec on its own,
and nanosvg is not a CSS engine). Rasterising such a file unmodified comes
out either solid black or fully invisible depending on the SDL_image
build. Fixed with a plain text substitution before rasterising:
`currentColor` is replaced with a concrete placeholder hex colour. The
placeholder itself is irrelevant -- exactly like `aircraft_icons._tint_surface`,
the rasterised icon is recoloured afterwards via a multiply-to-black-then-add
blend, which only cares about the alpha channel the rasteriser produced.

The same text pass also rewrites the source's own `width="24" height="24"`
root attributes to the requested `size_px` (the `viewBox="0 0 24 24"` stays
untouched -- that only defines the internal coordinate space, not the
raster resolution; nanosvg reads the root `width`/`height` attributes for
the latter). This rasterises directly at the target size instead of
loading at the source's native 24x24 and smoothscaling up afterwards --
the "matschig" upscale look this icon overhaul set out to get rid of --
and sidesteps `pygame.image.load_sized_svg`, which is not available on
every pygame build (a repo-wide check found no prior use of it, and the
installed pygame's vendor/version cannot be assumed).

Two-tier cache, mirroring `aircraft_icons.py`: a per-icon-key raw-SVG-text
cache (read from disk at most once), and a per-(icon_key, size_px, colour)
rendered-surface cache (rasterised+tinted at most once per unique
combination, never per frame). Unlike aircraft icons, UI icons are never
rotated by heading, so there is no angle-bucket dimension to the cache key.

`reset_cache()` clears both caches -- required because, like `fonts.py`'s
`Font` objects, a `pygame.Surface` built before a `pygame.quit()`/
`pygame.font.init()` cycle can become invalid afterwards; wired into
`flugradar/tests/conftest.py`'s autouse fixture the same way
`fonts.reset_cache()` already is. `aircraft_icons.py` itself has no such
reset and is not touched here -- see docs/ui-inventar.md for that gap.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Optional

import pygame

_ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "ui")

# Any opaque colour works here -- it is discarded by the multiply-to-black
# step in _tint_surface below, only the alpha channel the rasteriser
# produced survives into the final tinted icon.
_PLACEHOLDER_COLOUR = "#ffffff"

# icon_key -> raw SVG text with currentColor already substituted, or None
# if the file was missing/unreadable (loaded at most once per key).
_raw_svg_cache: dict[str, Optional[str]] = {}
# (icon_key, size_px, colour) -> final rasterised+tinted Surface (built at
# most once per unique combination, never per frame).
_render_cache: dict[tuple[str, int, tuple[int, int, int]], pygame.Surface] = {}
_warned_missing: set[str] = set()


def _warn_once(icon_key: str, reason: str) -> None:
    if icon_key in _warned_missing:
        return
    _warned_missing.add(icon_key)
    logging.getLogger(__name__).warning(
        "UI icon %r unavailable (%s); drawing placeholder instead", icon_key, reason,
    )


def _load_raw_svg(icon_key: str) -> Optional[str]:
    if icon_key in _raw_svg_cache:
        return _raw_svg_cache[icon_key]
    path = os.path.join(_ICON_DIR, f"{icon_key}.svg")
    text: Optional[str]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().replace("currentColor", _PLACEHOLDER_COLOUR)
    except (FileNotFoundError, OSError) as exc:
        _warn_once(icon_key, str(exc))
        text = None
    _raw_svg_cache[icon_key] = text
    return text


def _rasterise(icon_key: str, svg_text: str, size_px: int) -> Optional[pygame.Surface]:
    sized = (
        svg_text
        .replace('width="24"', f'width="{size_px}"', 1)
        .replace('height="24"', f'height="{size_px}"', 1)
    )
    try:
        surface = pygame.image.load(io.BytesIO(sized.encode("utf-8")), "icon.svg")
    except pygame.error as exc:
        _warn_once(icon_key, str(exc))
        return None
    if surface.get_size() != (size_px, size_px):
        surface = pygame.transform.smoothscale(surface, (size_px, size_px))
    return surface


def _tint_surface(surface: pygame.Surface, colour: tuple[int, int, int]) -> pygame.Surface:
    """Same recipe as aircraft_icons._tint_surface: multiply RGB to zero
    (alpha untouched, its multiplier is 255/255), then add the target
    colour (alpha untouched, its addend is 0). Works regardless of the
    placeholder colour rasterised above."""
    tinted = surface.copy()
    tinted.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    tinted.fill((*colour, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return tinted


def _draw_placeholder(size_px: int, colour: tuple[int, int, int]) -> pygame.Surface:
    """Fallback for a missing/broken icon file -- never crashes, and stays
    visibly distinct (a plain outlined square) from a real glyph so a
    missing asset is noticeable during development rather than silently
    blank."""
    surface = pygame.Surface((size_px, size_px), pygame.SRCALPHA)
    pygame.draw.rect(surface, colour, surface.get_rect(), width=max(1, size_px // 12))
    return surface


def get_icon(name: str, size_px: int, colour: tuple[int, int, int]) -> pygame.Surface:
    """Return a rasterised, recoloured icon Surface for `name` (the SVG
    filename under flugradar/assets/icons/ui/, without extension), cached
    beyond the first call for this exact (name, size_px, colour)."""
    cache_key = (name, size_px, colour)
    cached = _render_cache.get(cache_key)
    if cached is not None:
        return cached

    svg_text = _load_raw_svg(name)
    raw = _rasterise(name, svg_text, size_px) if svg_text is not None else None
    result = _tint_surface(raw, colour) if raw is not None else _draw_placeholder(size_px, colour)

    _render_cache[cache_key] = result
    return result


def draw_icon(
    surface: pygame.Surface,
    name: str,
    center: tuple[int, int],
    size_px: int,
    colour: tuple[int, int, int],
) -> None:
    icon = get_icon(name, size_px, colour)
    surface.blit(icon, icon.get_rect(center=center))


def reset_cache() -> None:
    """Drop every cached Surface -- required after a pygame.quit()/
    pygame.font.init() cycle, since a Surface built before it can become
    invalid afterwards (same reasoning as fonts.reset_cache())."""
    _raw_svg_cache.clear()
    _render_cache.clear()
    _warned_missing.clear()

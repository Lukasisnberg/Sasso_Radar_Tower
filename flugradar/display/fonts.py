"""Centralised font loading — Inter / IBM Plex Sans with fallbacks.

All screens MUST use get_font() instead of pygame.font.SysFont() directly,
so typography stays consistent across the entire UI.
"""

import pygame

_FONT_FAMILIES = (
    "Inter",
    "IBM Plex Sans",
    "DejaVu Sans",
    "Noto Sans",
    "FreeSans",
    "sans",
)

_MONO_FAMILIES = (
    "IBM Plex Mono",
    "JetBrains Mono",
    "DejaVu Sans Mono",
    "Noto Sans Mono",
    "FreeMono",
    "monospace",
)

_resolved: str | None = None
_resolved_mono: str | None = None

# (family, size, bold) -> Font. Several draw() paths (nav.py's breadcrumb
# and footer buttons, app.py's map attribution) call get_font() on every
# single frame rather than once at screen construction -- without this
# cache, that meant re-opening and re-parsing a TTF file via SDL_ttf 30
# times a second for as long as those screens were on-screen. The key
# space is small and fixed (a handful of TOKENS font sizes, each mono or
# not, each bold or not), so this can never grow unbounded.
_font_cache: dict[tuple[str, int, bool], pygame.font.Font] = {}


def _resolve_family(families: tuple[str, ...]) -> str:
    available = {n.lower() for n in pygame.font.get_fonts()}
    for name in families:
        normalised = name.lower().replace(" ", "")
        if normalised in available:
            return name
    return families[-1]


def get_font(size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
    global _resolved, _resolved_mono
    if mono:
        if _resolved_mono is None:
            _resolved_mono = _resolve_family(_MONO_FAMILIES)
        family = _resolved_mono
    else:
        if _resolved is None:
            _resolved = _resolve_family(_FONT_FAMILIES)
        family = _resolved

    key = (family, size, bold)
    font = _font_cache.get(key)
    if font is None:
        font = pygame.font.SysFont(family, size, bold=bold)
        _font_cache[key] = font
    return font


def reset_cache() -> None:
    """Drop every cached Font, plus the resolved family names.

    A pygame.font.Font created before pygame.quit() (which tears down
    SDL_ttf) is no longer valid afterwards even if the font subsystem is
    later reinitialized -- reusing it doesn't raise a catchable Python
    exception, it segfaults. Production code never exercises this path
    (pygame.quit() only ever runs once, at final app shutdown); this
    exists for test-suite isolation, where many independent test files
    share one process and each does its own pygame init/quit cycle.
    """
    global _resolved, _resolved_mono
    _font_cache.clear()
    _resolved = None
    _resolved_mono = None

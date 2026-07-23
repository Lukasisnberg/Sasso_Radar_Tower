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
    return pygame.font.SysFont(family, size, bold=bold)

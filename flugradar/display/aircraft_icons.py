"""Programmatic aircraft silhouettes by category for the radar display.

Draws top-down aircraft icons as filled polygons, rotated to heading.
Categories: jet (2/4-engine), helicopter, prop, military fighter, cargo.
Falls back to a generic airliner silhouette when type is unknown.
"""

from __future__ import annotations

import math
from typing import Optional

import pygame

from flugradar.display import scaling
from flugradar.display.theme import Theme

# Nose points toward -Y (north/up). Right-side outline, mirrored for left.
_JET_HALF = (
    (0.0, -13.0),
    (1.4, -12.7),
    (2.4, -12.0),
    (2.7, -10.5),
    (2.7, -6.0),
    (2.7, -4.5),
    (12.0, -0.8),
    (12.4, 0.6),
    (11.8, 2.2),
    (2.7, 3.4),
    (2.7, 8.5),
    (2.6, 10.2),
    (6.2, 11.4),
    (6.0, 12.2),
    (5.4, 12.6),
    (2.4, 12.8),
)

_HELICOPTER_HALF = (
    (0.0, -8.0),
    (1.8, -7.5),
    (2.5, -6.0),
    (2.5, -2.0),
    (2.5, 2.0),
    (2.5, 6.0),
    (1.8, 7.5),
    (0.0, 8.0),
)

_HELICOPTER_ROTOR_R = 10.0

_PROP_HALF = (
    (0.0, -10.0),
    (1.2, -9.5),
    (1.8, -8.0),
    (1.8, -4.0),
    (10.0, -1.5),
    (10.5, 0.0),
    (10.0, 1.5),
    (1.8, 3.0),
    (1.8, 7.0),
    (4.5, 8.5),
    (4.2, 9.2),
    (3.8, 9.5),
    (1.5, 9.8),
)

_FIGHTER_HALF = (
    (0.0, -12.0),
    (1.0, -11.5),
    (2.0, -10.0),
    (2.0, -5.0),
    (9.0, -1.0),
    (10.0, 0.5),
    (9.0, 2.0),
    (2.5, 3.0),
    (2.5, 8.0),
    (7.0, 10.0),
    (6.5, 11.0),
    (2.0, 11.5),
    (1.5, 12.0),
)

# Type code prefixes for classification
_FIGHTER_PREFIXES = (
    "F14", "F15", "F16", "F18", "F22", "F35", "F104", "F111", "F117",
    "EUFI", "RFAL", "HAWK", "TORN", "SU27", "SU30", "SU35", "MIG29", "MIG31",
    "JAS39", "M2K", "M346",
)
_HELI_PREFIXES = (
    "EC", "AS", "AW", "R4", "R6", "MI", "KA", "BK", "MD5",
    "H125", "H130", "H135", "H145", "H155", "H160", "H175", "H215", "H225",
)
_HELI_CODES = frozenset({
    "H47", "CH47", "H60", "UH1", "UH60", "MH60", "AH1", "AH64", "H64",
    "CH46", "CH53", "MH47", "MH53", "OH58", "TH67", "UH72",
    "B407", "B412", "B429", "S76", "S92", "R22", "R44", "R66",
    "A109", "A139", "AW139", "AW169", "AW189", "NH90", "AW101",
    "EC20", "EC25", "EC30", "EC35", "EC45", "EC55", "EC75",
})
_WIDE_BODY = frozenset({
    "A332", "A333", "A338", "A339", "A342", "A343", "A345", "A346",
    "A359", "A35K", "A380",
    "B744", "B748", "B762", "B763", "B764", "B772", "B773", "B77L", "B77W",
    "B788", "B789", "B78X",
    "IL96", "MD11", "DC10",
})
_PROP_CODES = frozenset({
    "C172", "C152", "C182", "C206", "C208", "C210", "C310", "C340", "C402", "C421",
    "PA28", "PA32", "PA34", "PA44", "PA46",
    "BE33", "BE35", "BE36", "BE58", "BE9L", "BE20", "B190", "B350",
    "SR20", "SR22", "S22T", "DA40", "DA42", "DA62",
    "PC12", "TBM7", "TBM8", "TBM9", "AT43", "AT45", "AT72", "AT75", "AT76",
    "DH8A", "DH8B", "DH8C", "DH8D", "SF34", "J328",
})


def classify_type(type_code: str) -> str:
    code = (type_code or "").upper().strip()
    if not code:
        return "jet"
    if code in _HELI_CODES:
        return "helicopter"
    for prefix in _HELI_PREFIXES:
        if code.startswith(prefix):
            return "helicopter"
    for prefix in _FIGHTER_PREFIXES:
        if code.startswith(prefix):
            return "fighter"
    if code in _PROP_CODES:
        return "prop"
    if code in _WIDE_BODY:
        return "wide"
    return "jet"


def _rotate(x: float, y: float, heading_deg: float) -> tuple[float, float]:
    rad = math.radians(heading_deg)
    sin_h = math.sin(rad)
    cos_h = math.cos(rad)
    return x * cos_h - y * sin_h, x * sin_h + y * cos_h


def _build_outline(half: tuple, scale: float) -> list[tuple[float, float]]:
    scaled = [(x * scale, y * scale) for x, y in half]
    outline = list(scaled)
    tail_y = max(y for _, y in half) * scale
    outline.append((0.0, tail_y))
    for x, y in reversed(scaled[1:]):
        outline.append((-x, y))
    return outline


def _draw_polygon(
    surface: pygame.Surface,
    cx: int, cy: int,
    heading_deg: float,
    color: tuple[int, int, int],
    half: tuple,
    scale: float,
) -> None:
    outline = _build_outline(half, scale)
    pts = []
    for lx, ly in outline:
        rx, ry = _rotate(lx, ly, heading_deg)
        pts.append((int(round(cx + rx)), int(round(cy + ry))))
    if len(pts) >= 3:
        pygame.draw.polygon(surface, color, pts)


def draw_plane_icon(
    surface: pygame.Surface,
    cx: int, cy: int,
    heading_deg: float,
    color: tuple[int, int, int],
    aircraft_type: str = "",
    compact: bool = False,
) -> None:
    category = classify_type(aircraft_type)
    if compact:
        base_scale = 0.40
    elif category == "wide":
        base_scale = 0.80
    elif category == "fighter":
        base_scale = 0.65
    else:
        base_scale = 0.68

    screen_scale = scaling.s(10) / 10.0
    scale = base_scale * screen_scale

    if category == "helicopter":
        _draw_polygon(surface, cx, cy, heading_deg, color, _HELICOPTER_HALF, scale)
        rotor_r = int(_HELICOPTER_ROTOR_R * scale)
        rx, ry = _rotate(0, -2 * scale, heading_deg)
        rotor_cx, rotor_cy = int(cx + rx), int(cy + ry)
        pygame.draw.circle(surface, color, (rotor_cx, rotor_cy), rotor_r, 1)
    elif category == "fighter":
        _draw_polygon(surface, cx, cy, heading_deg, color, _FIGHTER_HALF, scale)
    elif category == "prop":
        _draw_polygon(surface, cx, cy, heading_deg, color, _PROP_HALF, scale)
    else:
        _draw_polygon(surface, cx, cy, heading_deg, color, _JET_HALF, scale)


def format_altitude(alt_ft: Optional[int]) -> str:
    if alt_ft is None:
        return ""
    try:
        alt = int(alt_ft)
    except (TypeError, ValueError):
        return ""
    if alt <= 0:
        return ""
    if alt >= 18000:
        return f"FL{round(alt / 100)}"
    return f"{alt:,}ft"


def altitude_tag_color(
    vertical_rate_fpm: Optional[int],
    theme: Theme,
) -> tuple[int, int, int]:
    if vertical_rate_fpm is not None and vertical_rate_fpm < -64:
        return theme.tag_alt_descend
    return theme.tag_alt_ascend

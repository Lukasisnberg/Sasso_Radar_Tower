"""Programmatic aircraft silhouettes by category for the radar display.

Draws top-down aircraft icons as filled polygons, rotated to heading.
Categories: narrow-body jet, wide-body jet, prop/regional, helicopter,
military fighter, light/GA, glider, drone/UAV. Falls back to a plain
generic silhouette when neither ADS-B category nor type code resolve.
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

# Own silhouette (not a scaled _JET_HALF): noticeably wider fuselage collar
# and longer wings relative to overall length, plus a stepped radome nose.
_WIDE_HALF = (
    (0.0, -13.5),
    (1.8, -13.1),
    (3.2, -12.2),
    (3.7, -10.2),
    (3.7, -6.0),
    (3.7, -4.2),
    (15.0, -0.9),
    (15.5, 0.6),
    (14.8, 2.3),
    (3.7, 3.6),
    (3.7, 8.8),
    (3.5, 10.6),
    (7.8, 12.0),
    (7.5, 12.9),
    (6.6, 13.3),
    (3.0, 13.5),
)

# Small single-engine GA silhouette (Cessna-class): thin fuselage, short
# straight wing set well forward of centre, small tail.
_LIGHT_HALF = (
    (0.0, -7.0),
    (1.0, -6.5),
    (1.4, -5.0),
    (1.4, -1.0),
    (7.0, 0.0),
    (7.3, 0.8),
    (7.0, 1.6),
    (1.4, 2.6),
    (1.4, 5.5),
    (2.6, 6.5),
    (2.3, 7.0),
    (1.0, 7.2),
)

# Sailplane: very thin fuselage, extreme-aspect-ratio wing, no engine bulge.
_GLIDER_HALF = (
    (0.0, -9.0),
    (0.8, -8.5),
    (1.0, -6.0),
    (1.0, -1.0),
    (15.0, 0.0),
    (15.2, 0.6),
    (15.0, 1.0),
    (1.0, 2.0),
    (1.0, 7.0),
    (1.8, 8.0),
    (1.6, 8.6),
    (0.6, 8.8),
)

# Fixed-wing UAV: small overall, slender tapered fuselage, modest straight
# wing — deliberately smaller than every crewed category.
_DRONE_HALF = (
    (0.0, -6.0),
    (0.6, -5.6),
    (0.9, -4.0),
    (0.9, -1.0),
    (5.5, 0.0),
    (5.7, 0.6),
    (5.5, 1.0),
    (0.9, 2.0),
    (0.9, 4.5),
    (1.6, 5.5),
    (1.3, 6.0),
    (0.4, 6.2),
)

# Plain fallback silhouette for when neither category nor type code
# resolve — simpler than every named category, deliberately "generic".
_GENERIC_HALF = (
    (0.0, -10.0),
    (1.6, -8.0),
    (2.0, -4.0),
    (2.0, -1.5),
    (9.5, 1.0),
    (9.5, 2.2),
    (2.0, 2.0),
    (2.0, 6.5),
    (4.5, 8.5),
    (4.2, 9.2),
    (1.5, 8.8),
)

# ADS-B / Mode-S emitter category (DO-260B) -> icon category. "No info"
# codes (A0/B0/C0/D0) and reserved codes are omitted on purpose so callers
# fall through to the type-code classifier below.
_CATEGORY_CLASS: dict[str, str] = {
    "A1": "light",       # < 15,500 lbs
    "A2": "jet",          # 15,500-75,000 lbs
    "A3": "jet",           # 75,000-300,000 lbs
    "A4": "wide",           # high vortex large (e.g. B757)
    "A5": "wide",            # heavy, > 300,000 lbs
    "A6": "fighter",          # high performance / high speed
    "A7": "helicopter",       # rotorcraft
    "B1": "glider",           # glider / sailplane
    "B2": "generic",          # lighter-than-air
    "B3": "generic",          # parachutist / skydiver
    "B4": "light",            # ultralight / hang-glider / paraglider
    "B6": "drone",            # unmanned aerial vehicle
    "B7": "generic",          # space / trans-atmospheric vehicle
    "C1": "generic", "C2": "generic", "C3": "generic",
    "C4": "generic", "C5": "generic", "C6": "generic", "C7": "generic",
    "D1": "generic", "D2": "generic", "D3": "generic",
    "D4": "generic", "D5": "generic", "D6": "generic", "D7": "generic",
}

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


def _classify_by_type_code(type_code: str) -> str:
    code = (type_code or "").upper().strip()
    if not code:
        return "generic"
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


def classify_type(type_code: str = "", category: Optional[str] = None) -> str:
    """Resolve an icon category, preferring the ADS-B emitter category.

    The Mode-S `category` field (e.g. "A1".."B7") is the primary source
    since it reflects the aircraft's actual reported class. The type
    designator (e.g. "A320", "C172") is only used as a fallback when the
    category is missing or not one of the resolvable codes.
    """
    cat = (category or "").upper().strip()
    if cat in _CATEGORY_CLASS:
        return _CATEGORY_CLASS[cat]
    return _classify_by_type_code(type_code)


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
    category: Optional[str] = None,
    compact: bool = False,
) -> None:
    icon_category = classify_type(aircraft_type, category)
    if compact:
        base_scale = 0.40
    elif icon_category == "wide":
        base_scale = 0.80
    elif icon_category == "fighter":
        base_scale = 0.65
    elif icon_category == "light":
        base_scale = 0.50
    elif icon_category == "glider":
        base_scale = 0.55
    elif icon_category == "drone":
        base_scale = 0.42
    elif icon_category == "generic":
        base_scale = 0.62
    else:
        base_scale = 0.68

    screen_scale = scaling.s(10) / 10.0
    scale = base_scale * screen_scale

    if icon_category == "helicopter":
        _draw_polygon(surface, cx, cy, heading_deg, color, _HELICOPTER_HALF, scale)
        rotor_r = int(_HELICOPTER_ROTOR_R * scale)
        rx, ry = _rotate(0, -2 * scale, heading_deg)
        rotor_cx, rotor_cy = int(cx + rx), int(cy + ry)
        pygame.draw.circle(surface, color, (rotor_cx, rotor_cy), rotor_r, 1)
    elif icon_category == "fighter":
        _draw_polygon(surface, cx, cy, heading_deg, color, _FIGHTER_HALF, scale)
    elif icon_category == "prop":
        _draw_polygon(surface, cx, cy, heading_deg, color, _PROP_HALF, scale)
    elif icon_category == "wide":
        _draw_polygon(surface, cx, cy, heading_deg, color, _WIDE_HALF, scale)
    elif icon_category == "light":
        _draw_polygon(surface, cx, cy, heading_deg, color, _LIGHT_HALF, scale)
    elif icon_category == "glider":
        _draw_polygon(surface, cx, cy, heading_deg, color, _GLIDER_HALF, scale)
    elif icon_category == "drone":
        _draw_polygon(surface, cx, cy, heading_deg, color, _DRONE_HALF, scale)
    elif icon_category == "generic":
        _draw_polygon(surface, cx, cy, heading_deg, color, _GENERIC_HALF, scale)
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

"""Resolution-independent scaling for the round radar display.

All layout dimensions go through s() so the UI looks correct on any
square display (720×720 production, smaller dev windows, etc.).
"""

import math

REF_SIZE = 390

_size: int = 720
_scale: float = _size / REF_SIZE


def init(screen_size: int) -> None:
    global _size, _scale
    _size = screen_size
    _scale = _size / REF_SIZE


def s(value: float) -> int:
    return max(1, int(round(value * _scale)))


def size() -> int:
    return _size


def center_x() -> int:
    return _size // 2


def center_y() -> int:
    return _size // 2


def visible_radius() -> int:
    return _size // 2 - max(2, s(3))


def in_visible_circle(x: float, y: float, margin: float = 0) -> bool:
    dx = x - center_x()
    dy = y - center_y()
    limit = visible_radius() - margin
    return dx * dx + dy * dy <= limit * limit


def circle_half_width_at_row(row_y: int, row_h: int) -> int:
    r = visible_radius()
    if r <= 0 or row_h <= 0:
        return 0
    row_center = row_y + row_h // 2
    dy = row_center - center_y()
    if abs(dy) >= r:
        return 0
    half = math.sqrt(r * r - dy * dy)
    usable = int(half) - s(6)
    return max(0, usable)

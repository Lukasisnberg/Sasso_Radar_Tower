"""Hand-drawn weather-condition icons.

Vector-drawn with pygame primitives, following the project's existing
pattern for chrome that isn't licensed artwork (compass rose, sweep,
nav-button icons in `nav.py`) rather than pulling in a bitmap/SVG icon
set -- there's no license to track and no asset to ship.
"""

import math

import pygame

_CATEGORIES: dict[int, str] = {
    1000: "clear",
    1100: "clear",
    1101: "partly_cloudy",
    1102: "cloudy",
    1001: "cloudy",
    2000: "fog",
    2100: "fog",
    4000: "rain",
    4001: "rain",
    4200: "rain",
    4201: "rain",
    5000: "snow",
    5001: "snow",
    5100: "snow",
    5101: "snow",
    6000: "rain",
    6001: "rain",
    6200: "rain",
    6201: "rain",
    7000: "snow",
    7101: "snow",
    7102: "snow",
    8000: "thunderstorm",
}


def category_for_code(weather_code: int | None) -> str:
    return _CATEGORIES.get(weather_code, "cloudy")


def draw_weather_icon(
    surface: pygame.Surface,
    weather_code: int | None,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> None:
    """Draws a simple vector icon for the forecast category at `center`.
    `radius` is the overall icon half-size in already-scaled pixels;
    `color` is the cloud/fog body colour, `accent` highlights sun/rain/
    snow/bolt details (normally the theme's sweep colour)."""
    category = category_for_code(weather_code)
    cx, cy = center
    stroke = max(1, radius // 8)

    if category == "clear":
        _draw_sun(surface, (cx, cy), radius, accent)
    elif category == "partly_cloudy":
        _draw_sun(surface, (cx - radius // 3, cy - radius // 4), int(radius * 0.7), accent)
        _draw_cloud(surface, (cx + radius // 5, cy + radius // 5), radius, color)
    elif category == "fog":
        _draw_fog(surface, (cx, cy), radius, color, stroke)
    elif category == "rain":
        _draw_cloud(surface, (cx, cy - radius // 5), radius, color)
        _draw_rain_drops(surface, (cx, cy), radius, accent)
    elif category == "snow":
        _draw_cloud(surface, (cx, cy - radius // 5), radius, color)
        _draw_snow_flakes(surface, (cx, cy), radius, accent)
    elif category == "thunderstorm":
        _draw_cloud(surface, (cx, cy - radius // 5), radius, color)
        _draw_bolt(surface, (cx, cy), radius, accent)
    else:  # cloudy, and any unrecognised code
        _draw_cloud(surface, (cx, cy), radius, color)


def _draw_sun(surface, center, radius, color) -> None:
    cx, cy = center
    r = max(2, int(radius * 0.45))
    pygame.draw.circle(surface, color, (cx, cy), r)
    ray_len = int(radius * 0.35)
    ray_w = max(1, radius // 10)
    for i in range(8):
        angle = math.radians(i * 45)
        x0 = cx + int((r + 2) * math.cos(angle))
        y0 = cy + int((r + 2) * math.sin(angle))
        x1 = cx + int((r + 2 + ray_len) * math.cos(angle))
        y1 = cy + int((r + 2 + ray_len) * math.sin(angle))
        pygame.draw.line(surface, color, (x0, y0), (x1, y1), ray_w)


def _draw_cloud(surface, center, radius, color) -> None:
    cx, cy = center
    body_r = max(2, int(radius * 0.4))
    pygame.draw.circle(surface, color, (cx - body_r, cy), body_r)
    pygame.draw.circle(surface, color, (cx + int(body_r * 0.7), cy - int(body_r * 0.3)), int(body_r * 1.1))
    pygame.draw.circle(surface, color, (cx + body_r * 2, cy + int(body_r * 0.2)), int(body_r * 0.8))
    base_rect = pygame.Rect(cx - body_r * 2, cy, body_r * 4, body_r)
    pygame.draw.rect(surface, color, base_rect, border_radius=body_r)


def _draw_fog(surface, center, radius, color, stroke) -> None:
    cx, cy = center
    for i, dy in enumerate((-radius // 3, 0, radius // 3)):
        w = radius * (1.4 - i * 0.15)
        pygame.draw.line(
            surface, color,
            (int(cx - w / 2), cy + dy), (int(cx + w / 2), cy + dy),
            max(1, stroke),
        )


def _draw_rain_drops(surface, center, radius, color) -> None:
    cx, cy = center
    base_y = cy + int(radius * 0.35)
    width = max(1, radius // 8)
    for dx in (-radius * 0.35, 0, radius * 0.35):
        x = cx + int(dx)
        pygame.draw.line(
            surface, color,
            (x, base_y), (x - radius // 8, base_y + int(radius * 0.4)),
            width,
        )


def _draw_snow_flakes(surface, center, radius, color) -> None:
    cx, cy = center
    base_y = cy + int(radius * 0.4)
    r = max(1, radius // 10)
    for dx in (-radius * 0.35, 0, radius * 0.35):
        x = cx + int(dx)
        pygame.draw.circle(surface, color, (x, base_y), r)


def _draw_bolt(surface, center, radius, color) -> None:
    cx, cy = center
    pts = [
        (cx + radius * 0.1, cy + radius * 0.1),
        (cx - radius * 0.15, cy + radius * 0.5),
        (cx + radius * 0.05, cy + radius * 0.5),
        (cx - radius * 0.1, cy + radius * 0.9),
        (cx + radius * 0.3, cy + radius * 0.35),
        (cx + radius * 0.05, cy + radius * 0.35),
    ]
    pygame.draw.polygon(surface, color, [(int(x), int(y)) for x, y in pts])

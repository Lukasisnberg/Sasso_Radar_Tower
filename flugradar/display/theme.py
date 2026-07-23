"""Colour theme definitions with preset support and accent-derived palettes.

Extends the original dark/amber themes with multi-line tag colours,
alert colours, and a palette_from_rgb() factory that derives a full
theme from a single accent RGB.
"""

from dataclasses import dataclass


def _clamp(v: int) -> int:
    return max(0, min(255, v))


def _scale_color(base: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return (_clamp(int(round(base[0] * factor))),
            _clamp(int(round(base[1] * factor))),
            _clamp(int(round(base[2] * factor))))


@dataclass
class Theme:
    # --- core radar chrome ---
    background: tuple[int, int, int] = (11, 13, 15)
    radar_ring: tuple[int, int, int] = (40, 58, 60)
    radar_ring_alpha: int = 80
    sweep_colour: tuple[int, int, int] = (80, 180, 160)
    sweep_alpha_max: int = 60
    sweep_trail: tuple[int, int, int] = (20, 60, 45)
    compass_text: tuple[int, int, int] = (237, 239, 241)
    compass_tick: tuple[int, int, int] = (70, 85, 88)
    # --- aircraft rendering ---
    aircraft_dot: tuple[int, int, int] = (100, 210, 180)
    aircraft_label: tuple[int, int, int] = (180, 200, 195)
    aircraft_trail: tuple[int, int, int] = (50, 100, 85)
    aircraft_selected: tuple[int, int, int] = (210, 195, 120)
    emergency: tuple[int, int, int] = (200, 60, 60)
    heading_line: tuple[int, int, int] = (70, 140, 120)
    # --- multi-line tag colours ---
    tag_callsign: tuple[int, int, int] = (100, 210, 180)
    tag_type: tuple[int, int, int] = (255, 200, 0)
    tag_alt_ascend: tuple[int, int, int] = (0, 255, 255)
    tag_alt_descend: tuple[int, int, int] = (255, 0, 255)
    # --- alert system ---
    alert_military: tuple[int, int, int] = (255, 40, 40)
    alert_other: tuple[int, int, int] = (56, 160, 255)
    alert_flash: tuple[int, int, int] = (255, 80, 80)
    alert_flash_other: tuple[int, int, int] = (120, 200, 255)
    # --- UI chrome ---
    range_label: tuple[int, int, int] = (90, 110, 108)
    centre_dot: tuple[int, int, int] = (100, 180, 160)
    info_text: tuple[int, int, int] = (200, 210, 208)
    status_bar: tuple[int, int, int] = (90, 110, 108)
    hint: tuple[int, int, int] = (120, 140, 160)
    muted: tuple[int, int, int] = (180, 200, 220)
    route: tuple[int, int, int] = (100, 220, 255)
    page_dot_inactive: tuple[int, int, int] = (30, 40, 35)
    label: tuple[int, int, int] = (255, 255, 255)
    name: str = "dark"


def palette_from_rgb(r: int, g: int, b: int) -> dict[str, tuple[int, int, int]]:
    """Derive grid/sweep/trail/label colours from a single accent RGB."""
    base = (_clamp(r), _clamp(g), _clamp(b))
    label = (_clamp(int(round(base[0] + (255 - base[0]) * 0.18))),
             _clamp(int(round(base[1] + (255 - base[1]) * 0.18))),
             _clamp(int(round(base[2] + (255 - base[2]) * 0.18))))
    return {
        "grid": _scale_color(base, 0.72),
        "sweep": base,
        "sweep_trail": _scale_color(base, 0.28),
        "label": label,
    }


def theme_from_accent(r: int, g: int, b: int, name: str = "custom") -> Theme:
    pal = palette_from_rgb(r, g, b)
    return Theme(
        background=(2, 15, 3),
        radar_ring=pal["grid"],
        sweep_colour=pal["sweep"],
        sweep_trail=pal["sweep_trail"],
        compass_text=(237, 239, 241),
        compass_tick=pal["grid"],
        aircraft_dot=(255, 180, 40),
        aircraft_label=pal["label"],
        aircraft_trail=pal["sweep_trail"],
        aircraft_selected=(210, 195, 120),
        heading_line=_scale_color(pal["sweep"], 0.5),
        tag_callsign=pal["sweep"],
        range_label=pal["grid"],
        centre_dot=pal["sweep"],
        info_text=(210, 200, 175),
        status_bar=pal["grid"],
        page_dot_inactive=_scale_color(pal["grid"], 0.5),
        label=(255, 255, 255),
        name=name,
    )


DARK = Theme(
    background=(11, 13, 15),
    radar_ring=(40, 58, 60),
    sweep_colour=(80, 180, 160),
    sweep_trail=(20, 60, 45),
    compass_text=(237, 239, 241),
    compass_tick=(70, 85, 88),
    aircraft_dot=(100, 210, 180),
    aircraft_label=(180, 200, 195),
    aircraft_trail=(50, 100, 85),
    aircraft_selected=(210, 195, 120),
    heading_line=(70, 140, 120),
    tag_callsign=(100, 210, 180),
    range_label=(90, 110, 108),
    centre_dot=(100, 180, 160),
    info_text=(200, 210, 208),
    status_bar=(90, 110, 108),
    name="dark",
)

CLASSIC_AMBER = Theme(
    background=(13, 12, 10),
    radar_ring=(55, 48, 30),
    sweep_colour=(180, 155, 60),
    sweep_trail=(50, 42, 16),
    compass_text=(237, 225, 200),
    compass_tick=(85, 75, 45),
    aircraft_dot=(210, 180, 70),
    aircraft_label=(200, 190, 160),
    aircraft_trail=(100, 85, 40),
    aircraft_selected=(235, 220, 130),
    heading_line=(140, 120, 50),
    tag_callsign=(210, 180, 70),
    range_label=(110, 100, 65),
    centre_dot=(180, 155, 60),
    info_text=(210, 200, 175),
    status_bar=(110, 100, 65),
    hint=(140, 130, 100),
    muted=(200, 190, 160),
    route=(200, 180, 100),
    page_dot_inactive=(35, 30, 15),
    label=(237, 225, 200),
    name="amber",
)

RADAR_GREEN = theme_from_accent(48, 255, 96, name="green")
RADAR_RED = theme_from_accent(255, 64, 64, name="red")
RADAR_YELLOW = theme_from_accent(255, 255, 64, name="yellow")
RADAR_WHITE = theme_from_accent(255, 255, 255, name="white")

THEMES: dict[str, Theme] = {
    "dark": DARK,
    "amber": CLASSIC_AMBER,
    "green": RADAR_GREEN,
    "red": RADAR_RED,
    "yellow": RADAR_YELLOW,
    "white": RADAR_WHITE,
}

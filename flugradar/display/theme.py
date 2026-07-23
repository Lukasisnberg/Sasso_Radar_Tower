"""Colour theme definitions for the radar display.

Palette follows a "less but better" design language: dark anthracite
background (not pure black), warm off-white text, a single muted teal
accent for active/primary elements, red reserved exclusively for
genuine emergencies (squawk 7500/7600/7700).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    background: tuple[int, int, int]
    radar_ring: tuple[int, int, int]
    radar_ring_alpha: int
    sweep_colour: tuple[int, int, int]
    sweep_alpha_max: int
    compass_text: tuple[int, int, int]
    compass_tick: tuple[int, int, int]
    aircraft_dot: tuple[int, int, int]
    aircraft_label: tuple[int, int, int]
    aircraft_trail: tuple[int, int, int]
    aircraft_selected: tuple[int, int, int]
    emergency: tuple[int, int, int]
    heading_line: tuple[int, int, int]
    range_label: tuple[int, int, int]
    centre_dot: tuple[int, int, int]
    info_text: tuple[int, int, int]
    status_bar: tuple[int, int, int]


DARK = Theme(
    background=(11, 13, 15),          # #0B0D0F — dark anthracite
    radar_ring=(40, 58, 60),          # muted teal hairline
    radar_ring_alpha=80,
    sweep_colour=(80, 180, 160),      # desaturated teal sweep
    sweep_alpha_max=60,
    compass_text=(237, 239, 241),     # #EDEFF1 — warm off-white
    compass_tick=(70, 85, 88),        # subtle tick marks
    aircraft_dot=(100, 210, 180),     # muted teal-green
    aircraft_label=(180, 200, 195),   # soft off-white
    aircraft_trail=(50, 100, 85),     # dim trail
    aircraft_selected=(210, 195, 120),# warm gold highlight
    emergency=(200, 60, 60),          # reserved for real alerts only
    heading_line=(70, 140, 120),      # subtle heading indicator
    range_label=(90, 110, 108),       # subdued label
    centre_dot=(100, 180, 160),       # teal centre mark
    info_text=(200, 210, 208),        # near-white for data values
    status_bar=(90, 110, 108),        # subdued status text
)

CLASSIC_AMBER = Theme(
    background=(13, 12, 10),          # warm dark
    radar_ring=(55, 48, 30),          # muted amber ring
    radar_ring_alpha=80,
    sweep_colour=(180, 155, 60),      # desaturated gold sweep
    sweep_alpha_max=60,
    compass_text=(237, 225, 200),     # warm off-white
    compass_tick=(85, 75, 45),        # subtle amber tick
    aircraft_dot=(210, 180, 70),      # muted gold
    aircraft_label=(200, 190, 160),   # soft warm text
    aircraft_trail=(100, 85, 40),     # dim amber trail
    aircraft_selected=(235, 220, 130),# bright gold highlight
    emergency=(200, 60, 60),          # same alert red
    heading_line=(140, 120, 50),      # subtle heading
    range_label=(110, 100, 65),       # subdued label
    centre_dot=(180, 155, 60),        # amber centre
    info_text=(210, 200, 175),        # warm data text
    status_bar=(110, 100, 65),        # subdued status
)

THEMES: dict[str, Theme] = {
    "dark": DARK,
    "amber": CLASSIC_AMBER,
}

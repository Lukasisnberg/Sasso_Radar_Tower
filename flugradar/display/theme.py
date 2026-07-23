"""Colour theme definitions for the radar display."""

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
    background=(10, 15, 10),
    radar_ring=(0, 60, 0),
    radar_ring_alpha=120,
    sweep_colour=(0, 200, 0),
    sweep_alpha_max=80,
    compass_text=(0, 180, 0),
    compass_tick=(0, 100, 0),
    aircraft_dot=(0, 255, 80),
    aircraft_label=(0, 220, 60),
    aircraft_trail=(0, 120, 40),
    aircraft_selected=(255, 255, 0),
    emergency=(255, 40, 40),
    heading_line=(0, 160, 0),
    range_label=(0, 140, 0),
    centre_dot=(0, 200, 0),
    info_text=(0, 180, 0),
    status_bar=(0, 160, 0),
)

CLASSIC_AMBER = Theme(
    background=(10, 10, 5),
    radar_ring=(60, 50, 0),
    radar_ring_alpha=120,
    sweep_colour=(200, 170, 0),
    sweep_alpha_max=80,
    compass_text=(200, 170, 0),
    compass_tick=(120, 100, 0),
    aircraft_dot=(255, 200, 0),
    aircraft_label=(240, 190, 0),
    aircraft_trail=(140, 110, 0),
    aircraft_selected=(255, 255, 100),
    emergency=(255, 40, 40),
    heading_line=(180, 150, 0),
    range_label=(160, 130, 0),
    centre_dot=(220, 180, 0),
    info_text=(200, 170, 0),
    status_bar=(180, 150, 0),
)

THEMES: dict[str, Theme] = {
    "dark": DARK,
    "amber": CLASSIC_AMBER,
}

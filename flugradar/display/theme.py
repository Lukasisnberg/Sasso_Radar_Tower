"""Colour themes and shared design tokens.

Ausbaustufe 2, Schritt 1 (docs/prompt-ausbaustufe-2.md): reduced from six
themes down to exactly two -- "amber" (default, warm/muted gold accent)
and "mono" (neutral off-white accent). Both share an identical dark
anthracite background and neutral text colours; only the accent hue
differs, built from one shared _theme_from_accent() so the two can't
silently drift apart. Warning/alert colours are semantic, not
accent-tinted, and are therefore left as plain Theme defaults shared
unchanged by both themes.

Also introduces the central design tokens (spacing grid, font-size
tiers, stroke width, animation timing/easing) referenced from Schritt
1.1 -- meant to be the single source for these values across the
renderer/screens instead of scattered literals.
"""

from dataclasses import dataclass


def _clamp(v: int) -> int:
    return max(0, min(255, v))


def _scale_color(base: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return (_clamp(int(round(base[0] * factor))),
            _clamp(int(round(base[1] * factor))),
            _clamp(int(round(base[2] * factor))))


def _lighten(base: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(_clamp(int(round(c + (255 - c) * factor))) for c in base)


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Linear-interpolate from `a` (t=0) to `b` (t=1)."""
    return tuple(_clamp(int(round(a[i] + (b[i] - a[i]) * t))) for i in range(3))


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
    # --- multi-line tag colours (semantic, not accent-tinted) ---
    tag_callsign: tuple[int, int, int] = (100, 210, 180)
    tag_type: tuple[int, int, int] = (255, 200, 0)
    tag_alt_ascend: tuple[int, int, int] = (0, 255, 255)
    tag_alt_descend: tuple[int, int, int] = (255, 0, 255)
    # --- alert system (semantic, not accent-tinted) ---
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
    # --- raised-panel fills (footer buttons, cards) ---
    surface: tuple[int, int, int] = (18, 21, 24)
    surface_accent: tuple[int, int, int] = (22, 27, 26)
    name: str = "amber"


def _theme_from_accent(accent: tuple[int, int, int], name: str) -> Theme:
    """Build a full theme from a single accent colour.

    Background, neutral text, and semantic tag/alert colours are fixed
    and shared by every theme; only accent-tinted chrome (sweep, grid,
    aircraft dot/selection, callsign tag, centre dot, heading line) is
    derived from `accent`. This guarantees "amber" and "mono" can only
    ever differ in accent, per Schritt 1.2.
    """
    grid = _scale_color(accent, 0.55)
    trail = _scale_color(accent, 0.28)
    background = (11, 13, 15)
    return Theme(
        background=background,
        radar_ring=grid,
        sweep_colour=accent,
        sweep_trail=trail,
        compass_text=(230, 232, 230),
        compass_tick=grid,
        aircraft_dot=accent,
        aircraft_label=(190, 195, 192),
        aircraft_trail=trail,
        aircraft_selected=_lighten(accent, 0.25),
        heading_line=_scale_color(accent, 0.65),
        tag_callsign=accent,
        range_label=grid,
        centre_dot=accent,
        info_text=(205, 208, 205),
        status_bar=grid,
        hint=(150, 155, 152),
        muted=(180, 185, 182),
        route=accent,
        page_dot_inactive=_scale_color(grid, 0.5),
        label=(235, 235, 233),
        surface=_lighten(background, 0.06),
        surface_accent=_blend(background, trail, 0.55),
        name=name,
    )


# Warm, muted gold/amber -- the default theme.
CLASSIC_AMBER = _theme_from_accent((210, 180, 70), name="amber")

# Neutral, desaturated off-white -- maximally reduced, no hue at all.
MONO = _theme_from_accent((222, 222, 220), name="mono")

THEMES: dict[str, Theme] = {
    "amber": CLASSIC_AMBER,
    "mono": MONO,
}


def resolve_theme(name: str) -> Theme:
    """Look up a theme by name.

    Falls back to "amber" silently for unknown/removed names (e.g. an
    old settings.json still referencing a theme from before the
    reduction to two) -- no error, no blank screen.
    """
    return THEMES.get(name, CLASSIC_AMBER)


@dataclass(frozen=True)
class DesignTokens:
    """Central design constants -- spacing grid, font-size tiers, stroke
    width, animation timing/easing. Meant to be referenced from screens
    and the renderer instead of scattering literal values (Schritt 1.1);
    wiring every screen onto these is the job of the later polish pass
    (Schritt 3), not this step.
    """
    grid_unit: int = 4            # base spacing grid, reference px (feed through scaling.s())
    font_title: int = 14          # screen titles / large headline values
    font_value: int = 11          # primary data values (altitude, speed, callsign)
    font_standard: int = 9        # body/standard text
    font_small: int = 7           # secondary/detail text
    line_stroke: int = 2          # icon outlines, dividers
    hairline_alpha: int = 60      # low-opacity hairline dividers (out of 255)
    duration_short_ms: int = 150  # tap feedback
    duration_long_ms: int = 350   # screen/layer transitions
    easing: str = "ease_out_cubic"


TOKENS = DesignTokens()


def ease_out_cubic(t: float) -> float:
    """The one shared easing curve named by TOKENS.easing. t in [0, 1]."""
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3

"""Fixed home-location presets for the on-device Standort menu.

Ausbaustufe 2, Schritt 4 (docs/prompt-ausbaustufe-2.md, 4.2) intentionally
limits this to exactly two hardcoded locations -- no search, no on-screen
keyboard, no geocoding. Coordinates are looked-up + sourced, not guessed;
see the comment on each entry.
"""

from dataclasses import dataclass

# How close (in degrees) settings.home must be to a preset's coordinates to
# count as "currently selected" in the menu, vs. a portal-set custom value.
MATCH_EPSILON_DEG = 1e-4


@dataclass(frozen=True)
class LocationPreset:
    key: str
    label: str
    lat: float
    lon: float


LOCATIONS: tuple[LocationPreset, ...] = (
    # Gießen, Hesse, DE -- city centre. Cross-checked across latitude.to and
    # latlong.info (agree to 5 decimal places).
    LocationPreset(key="giessen", label="Gießen, DE", lat=50.58727, lon=8.67554),
    # Sassofortino, frazione of Roccastrada, Provincia di Grosseto, IT.
    # Source: Wikipedia infobox coordinates (en.wikipedia.org/wiki/Sassofortino).
    LocationPreset(key="sassofortino", label="Sassofortino, IT", lat=43.02583, lon=11.11222),
)

RADIUS_PRESETS_KM: tuple[float, ...] = (25.0, 50.0, 100.0, 150.0, 250.0)


def resolve_location(key: str) -> LocationPreset | None:
    for loc in LOCATIONS:
        if loc.key == key:
            return loc
    return None


def current_location_key(lat: float, lon: float) -> str | None:
    """Which preset (if any) the given coordinates currently match."""
    for loc in LOCATIONS:
        if abs(loc.lat - lat) < MATCH_EPSILON_DEG and abs(loc.lon - lon) < MATCH_EPSILON_DEG:
            return loc.key
    return None

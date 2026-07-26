"""Pure math for the tracked-flight progress bar (Ausbaustufe 2, Schritt 5).

No pygame, no I/O -- takes plain coordinates/speeds and returns plain
numbers so it's trivially unit-testable and reusable from both the
display screen and (if ever wanted) the web portal.
"""

from typing import Optional

from flugradar.data_sources.geo import haversine_km

KT_TO_KMH = 1.852


def route_progress_fraction(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    cur_lat: float, cur_lon: float,
) -> float:
    """0.0-1.0 fraction of the route already flown, clamped both ends so an
    aircraft that overshoots the destination (or a great-circle shortcut
    that undershoots) never produces a bar past either edge."""
    total_km = haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
    if total_km <= 0:
        return 1.0
    remaining_km = haversine_km(cur_lat, cur_lon, dest_lat, dest_lon)
    travelled_km = total_km - remaining_km
    return max(0.0, min(1.0, travelled_km / total_km))


def remaining_distance_km(
    cur_lat: float, cur_lon: float, dest_lat: float, dest_lon: float,
) -> float:
    return haversine_km(cur_lat, cur_lon, dest_lat, dest_lon)


def remaining_time_s(remaining_km: float, ground_speed_kt: Optional[float]) -> Optional[float]:
    """None if speed is unknown/zero -- there's no meaningful ETA to show,
    not an infinite or undefined one."""
    if not ground_speed_kt or ground_speed_kt <= 0:
        return None
    speed_kmh = ground_speed_kt * KT_TO_KMH
    return (remaining_km / speed_kmh) * 3600.0


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total_min = round(seconds / 60.0)
    h, m = divmod(total_min, 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def vertical_rate_label(vertical_rate_fpm: Optional[int], level_threshold_fpm: int = 100) -> str:
    """A direction word, not just a signed number -- +/-100fpm reads as
    noise/rounding on most feeds, not a real climb or descent."""
    if vertical_rate_fpm is None:
        return ""
    if vertical_rate_fpm > level_threshold_fpm:
        return "Steigflug"
    if vertical_rate_fpm < -level_threshold_fpm:
        return "Sinkflug"
    return "Horizontalflug"

"""Unit tests for the tracked-flight progress math (Ausbaustufe 2, Schritt 5)."""

import pytest

from flugradar.data_sources.route_progress import (
    format_duration,
    remaining_distance_km,
    remaining_time_s,
    route_progress_fraction,
    vertical_rate_label,
)

# Frankfurt (FRA) -> JFK, a real long-haul route, coordinates from adsbdb.
FRA = (50.033333, 8.570556)
JFK = (40.639801, -73.7789)


def _midpoint(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


class TestRouteProgressFraction:
    def test_at_origin_is_zero(self):
        frac = route_progress_fraction(*FRA, *JFK, *FRA)
        assert frac == pytest.approx(0.0, abs=1e-6)

    def test_at_destination_is_one(self):
        frac = route_progress_fraction(*FRA, *JFK, *JFK)
        assert frac == pytest.approx(1.0, abs=1e-6)

    def test_roughly_midway_is_roughly_half(self):
        mid = _midpoint(FRA, JFK)
        frac = route_progress_fraction(*FRA, *JFK, *mid)
        # not exact -- a lat/lon midpoint isn't exactly the great-circle
        # midpoint -- but should be close for a gut-check
        assert 0.4 < frac < 0.6

    def test_never_exceeds_one_even_past_the_destination(self):
        # a point further from origin than the destination itself (flew past
        # it) -- distance-to-destination is symmetric in both directions, so
        # this metric can't tell "just short of" from "just past", but the
        # displayed bar must never read over 100% either way (5.3)
        overshoot = (JFK[0] + (JFK[0] - FRA[0]) * 0.1, JFK[1] + (JFK[1] - FRA[1]) * 0.1)
        frac = route_progress_fraction(*FRA, *JFK, *overshoot)
        assert 0.0 <= frac <= 1.0

    def test_clamped_when_behind_origin(self):
        behind = (FRA[0] - (JFK[0] - FRA[0]) * 0.1, FRA[1] - (JFK[1] - FRA[1]) * 0.1)
        frac = route_progress_fraction(*FRA, *JFK, *behind)
        assert frac == 0.0

    def test_zero_length_route_reports_arrived(self):
        frac = route_progress_fraction(*FRA, *FRA, *FRA)
        assert frac == 1.0


class TestRemainingDistanceAndTime:
    def test_remaining_distance_at_destination_is_zero(self):
        assert remaining_distance_km(*JFK, *JFK) == pytest.approx(0.0, abs=1e-6)

    def test_remaining_distance_positive_en_route(self):
        mid = _midpoint(FRA, JFK)
        km = remaining_distance_km(*mid, *JFK)
        assert km > 0

    def test_remaining_time_scales_inversely_with_speed(self):
        slow = remaining_time_s(1000.0, 100.0)
        fast = remaining_time_s(1000.0, 500.0)
        assert slow > fast

    def test_remaining_time_none_when_speed_is_zero(self):
        assert remaining_time_s(500.0, 0.0) is None

    def test_remaining_time_none_when_speed_is_none(self):
        assert remaining_time_s(500.0, None) is None

    def test_remaining_time_none_when_speed_negative(self):
        assert remaining_time_s(500.0, -5.0) is None

    def test_remaining_time_sane_value(self):
        # 926 km at 500 kt (~926 km/h) should take roughly an hour
        seconds = remaining_time_s(926.0, 500.0)
        assert 3400 < seconds < 3800


class TestFormatDuration:
    def test_under_an_hour(self):
        assert format_duration(25 * 60) == "25m"

    def test_over_an_hour(self):
        assert format_duration(90 * 60) == "1h 30m"

    def test_none_is_placeholder(self):
        assert format_duration(None) == "—"

    def test_negative_is_placeholder(self):
        assert format_duration(-5) == "—"

    def test_rounds_to_nearest_minute(self):
        assert format_duration(89 * 60 + 40) == "1h 30m"


class TestVerticalRateLabel:
    def test_climbing(self):
        assert vertical_rate_label(1500) == "climbing"

    def test_descending(self):
        assert vertical_rate_label(-1200) == "descending"

    def test_level_flight(self):
        assert vertical_rate_label(0) == "level"

    def test_small_noise_reads_as_level(self):
        assert vertical_rate_label(50) == "level"
        assert vertical_rate_label(-50) == "level"

    def test_none_is_empty(self):
        assert vertical_rate_label(None) == ""

    def test_custom_threshold(self):
        assert vertical_rate_label(150, level_threshold_fpm=200) == "level"
        assert vertical_rate_label(250, level_threshold_fpm=200) == "climbing"

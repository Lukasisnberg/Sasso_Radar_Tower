"""Unit tests for the reduced 2-theme system and design tokens."""

import dataclasses

import pytest

from flugradar.display.theme import (
    CLASSIC_AMBER,
    MONO,
    TOKENS,
    THEMES,
    Theme,
    resolve_theme,
)


class TestThemeSet:
    def test_exactly_two_themes(self):
        assert set(THEMES.keys()) == {"amber", "mono"}

    def test_amber_is_named_amber(self):
        assert CLASSIC_AMBER.name == "amber"

    def test_mono_is_named_mono(self):
        assert MONO.name == "mono"

    @pytest.mark.parametrize("theme", [CLASSIC_AMBER, MONO])
    def test_theme_has_no_missing_fields(self, theme):
        # Every Theme field must be set to something -- a dataclass
        # instance can't have "missing" fields, but this guards against a
        # future field being added without a value on one of the presets.
        for f in dataclasses.fields(Theme):
            assert getattr(theme, f.name) is not None

    def test_both_share_the_same_dark_background(self):
        assert CLASSIC_AMBER.background == MONO.background

    def test_only_the_accent_differs(self):
        # Every accent-tinted field must differ between the two themes...
        accent_fields = [
            "sweep_colour", "aircraft_dot", "aircraft_selected",
            "tag_callsign", "centre_dot", "heading_line",
            "radar_ring", "range_label", "status_bar", "compass_tick",
        ]
        for f in accent_fields:
            assert getattr(CLASSIC_AMBER, f) != getattr(MONO, f), f

        # ...while shared/semantic fields must be identical.
        shared_fields = [
            "background", "emergency", "tag_type",
            "tag_alt_ascend", "tag_alt_descend",
            "alert_military", "alert_other", "alert_flash", "alert_flash_other",
        ]
        for f in shared_fields:
            assert getattr(CLASSIC_AMBER, f) == getattr(MONO, f), f

    def test_mono_accent_is_desaturated(self):
        r, g, b = MONO.sweep_colour
        assert max(r, g, b) - min(r, g, b) <= 4  # near-neutral, no real hue


class TestResolveTheme:
    def test_known_names_resolve(self):
        assert resolve_theme("amber") is CLASSIC_AMBER
        assert resolve_theme("mono") is MONO

    @pytest.mark.parametrize("removed_name", ["dark", "green", "red", "yellow", "white", ""])
    def test_unknown_or_removed_name_falls_back_to_amber(self, removed_name):
        assert resolve_theme(removed_name) is CLASSIC_AMBER

    def test_none_falls_back_to_amber(self):
        assert resolve_theme(None) is CLASSIC_AMBER


class TestDesignTokens:
    def test_at_most_four_font_tiers(self):
        sizes = {TOKENS.font_title, TOKENS.font_value, TOKENS.font_standard, TOKENS.font_small}
        assert len(sizes) <= 4

    def test_font_tiers_are_distinct_and_descending(self):
        assert TOKENS.font_title > TOKENS.font_value > TOKENS.font_standard > TOKENS.font_small

    def test_two_animation_durations(self):
        assert TOKENS.duration_short_ms < TOKENS.duration_long_ms

    def test_grid_unit_positive(self):
        assert TOKENS.grid_unit > 0


class TestEasing:
    def test_ease_out_cubic_endpoints(self):
        from flugradar.display.theme import ease_out_cubic
        assert ease_out_cubic(0.0) == pytest.approx(0.0)
        assert ease_out_cubic(1.0) == pytest.approx(1.0)

    def test_ease_out_cubic_clamps_out_of_range(self):
        from flugradar.display.theme import ease_out_cubic
        assert ease_out_cubic(-1.0) == pytest.approx(0.0)
        assert ease_out_cubic(2.0) == pytest.approx(1.0)

    def test_ease_out_cubic_monotonic(self):
        from flugradar.display.theme import ease_out_cubic
        prev = -1.0
        for i in range(11):
            t = i / 10
            val = ease_out_cubic(t)
            assert val >= prev
            prev = val

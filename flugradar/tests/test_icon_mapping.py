"""Unit tests for ICAO type-code / ADS-B category -> icon resolution."""

import pytest

from flugradar.display.icon_mapping import (
    CATEGORY_TO_ICON,
    GENERIC_ICON,
    TYPE_CODE_TO_ICON,
    resolve_icon,
)


class TestTypeCodeResolution:
    @pytest.mark.parametrize(
        "type_code,expected",
        [
            ("A320", "a320"),
            ("a320", "a320"),  # case-insensitive
            ("C172", "cessna"),
            ("B738", "b767"),  # source's own tooltip groups B738 under b767
            ("GLF5", "glf5"),
            ("MD11", "md11"),  # manual fix for source's copy-paste bug
            ("CRJ900", "crjx"),  # resolved conflict: specific icon wins
            ("B78X", "b787"),
        ],
    )
    def test_exact_type_code_match(self, type_code, expected):
        assert resolve_icon(type_code) == expected

    def test_military_prefix_wins_regardless_of_category(self):
        # F16 has no entry in TYPE_CODE_TO_ICON (no fighter type codes in
        # the source's tooltips), but must still resolve to the fighter
        # icon even if category claims something else entirely.
        assert "F16" not in TYPE_CODE_TO_ICON
        assert resolve_icon("F16", category="A1") == "a6"

    def test_exact_type_match_takes_priority_over_category(self):
        assert resolve_icon("A320", category="A7") == "a320"


class TestCategoryFallback:
    @pytest.mark.parametrize(
        "category,expected",
        [
            ("A1", "a1"),
            ("A7", "a7"),
            ("B1", "b1"),
            ("B6", "b0"),  # no dedicated drone/UAV icon in the source set
            ("B7", "b0"),
            ("C3", "c0"),
            ("D5", "c0"),
        ],
    )
    def test_unknown_type_falls_back_to_category(self, category, expected):
        assert resolve_icon("", category) == expected
        assert resolve_icon("ZZZZ9", category) == expected

    def test_type_code_still_wins_when_category_is_no_info(self):
        # A0 ("no ADS-B emitter category information") does map to a0.svg
        # in CATEGORY_TO_ICON, but type-code resolution runs first, so a
        # known type code still wins over a "no info" category.
        assert CATEGORY_TO_ICON["A0"] == "a0"
        assert resolve_icon("C172", "A0") == "cessna"


class TestGenericFallback:
    def test_nothing_known_returns_generic(self):
        assert resolve_icon() == GENERIC_ICON
        assert resolve_icon("", None) == GENERIC_ICON

    def test_unresolvable_type_and_category(self):
        assert resolve_icon("ZZZZ9", "Q9") == GENERIC_ICON

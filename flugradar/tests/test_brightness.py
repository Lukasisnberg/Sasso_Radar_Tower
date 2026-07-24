"""Unit tests for software screen dimming (Ausbaustufe 2, Schritt 4)."""

import datetime
from dataclasses import dataclass

import pygame
import pytest

from flugradar.display.brightness import (
    apply_dim_overlay,
    effective_brightness,
    within_time_window,
)


class TestWithinTimeWindow:
    def test_simple_window_inside(self):
        assert within_time_window("09:00", "17:00", now=datetime.time(12, 0)) is True

    def test_simple_window_outside(self):
        assert within_time_window("09:00", "17:00", now=datetime.time(20, 0)) is False

    def test_wraps_past_midnight_inside_late(self):
        assert within_time_window("22:00", "06:00", now=datetime.time(23, 30)) is True

    def test_wraps_past_midnight_inside_early(self):
        assert within_time_window("22:00", "06:00", now=datetime.time(2, 0)) is True

    def test_wraps_past_midnight_outside(self):
        assert within_time_window("22:00", "06:00", now=datetime.time(12, 0)) is False

    def test_malformed_value_returns_false_not_crash(self):
        assert within_time_window("garbage", "06:00", now=datetime.time(2, 0)) is False
        assert within_time_window("", "", now=datetime.time(2, 0)) is False


@dataclass
class _FakeSettings:
    brightness: int = 100
    night_mode_enabled: bool = False
    night_mode_start: str = "22:00"
    night_mode_end: str = "06:00"
    night_mode_brightness: int = 30


class TestEffectiveBrightness:
    def test_night_mode_off_uses_plain_brightness(self):
        s = _FakeSettings(brightness=80, night_mode_enabled=False)
        assert effective_brightness(s, now=datetime.time(23, 0)) == 80

    def test_night_mode_on_but_outside_window_uses_plain_brightness(self):
        s = _FakeSettings(brightness=80, night_mode_enabled=True)
        assert effective_brightness(s, now=datetime.time(12, 0)) == 80

    def test_night_mode_caps_brightness_inside_window(self):
        s = _FakeSettings(brightness=80, night_mode_enabled=True, night_mode_brightness=30)
        assert effective_brightness(s, now=datetime.time(23, 0)) == 30

    def test_night_mode_does_not_raise_brightness(self):
        # if plain brightness is already lower than the night cap, keep it
        s = _FakeSettings(brightness=10, night_mode_enabled=True, night_mode_brightness=30)
        assert effective_brightness(s, now=datetime.time(23, 0)) == 10

    def test_clamped_to_0_100(self):
        s = _FakeSettings(brightness=500, night_mode_enabled=False)
        assert effective_brightness(s, now=datetime.time(12, 0)) == 100


class TestApplyDimOverlay:
    @pytest.fixture(autouse=True)
    def init_pygame(self):
        pygame.init()
        yield
        pygame.quit()

    def test_full_brightness_is_a_no_op(self):
        surf = pygame.Surface((10, 10))
        surf.fill((200, 200, 200))
        apply_dim_overlay(surf, 100)
        assert surf.get_at((5, 5))[:3] == (200, 200, 200)

    def test_dims_towards_black(self):
        surf = pygame.Surface((10, 10))
        surf.fill((200, 200, 200))
        apply_dim_overlay(surf, 0)
        r, g, b, *_ = surf.get_at((5, 5))
        assert (r, g, b) == (0, 0, 0)

    def test_partial_brightness_darkens_but_does_not_black_out(self):
        surf = pygame.Surface((10, 10))
        surf.fill((200, 200, 200))
        apply_dim_overlay(surf, 50)
        r, g, b, *_ = surf.get_at((5, 5))
        assert 0 < r < 200

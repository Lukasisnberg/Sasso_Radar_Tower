"""Tests for shared drawing helpers, notably render_tracked_text() (added
for the weather screen's letter-spaced all-caps labels)."""

import pygame
import pytest

from flugradar.display.draw_helpers import render_tracked_text


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((100, 100))
    yield
    pygame.quit()


@pytest.fixture
def font():
    return pygame.font.SysFont(None, 20)


class TestRenderTrackedText:
    def test_zero_spacing_matches_plain_render(self, font):
        tracked = render_tracked_text(font, "ABC", (255, 255, 255), spacing=0)
        plain = font.render("ABC", True, (255, 255, 255))
        assert tracked.get_size() == plain.get_size()

    def test_positive_spacing_is_wider_than_plain_render(self, font):
        tracked = render_tracked_text(font, "ABC", (255, 255, 255), spacing=5)
        plain = font.render("ABC", True, (255, 255, 255))
        assert tracked.get_width() > plain.get_width()

    def test_more_spacing_is_wider(self, font):
        small = render_tracked_text(font, "ABC", (255, 255, 255), spacing=2)
        large = render_tracked_text(font, "ABC", (255, 255, 255), spacing=10)
        assert large.get_width() > small.get_width()

    def test_single_character_ignores_spacing(self, font):
        tracked = render_tracked_text(font, "A", (255, 255, 255), spacing=10)
        plain = font.render("A", True, (255, 255, 255))
        assert tracked.get_size() == plain.get_size()

    def test_empty_string_does_not_crash(self, font):
        surf = render_tracked_text(font, "", (255, 255, 255), spacing=5)
        assert surf.get_width() == 0

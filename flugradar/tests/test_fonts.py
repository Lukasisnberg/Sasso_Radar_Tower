"""Tests for the shared font cache (flugradar/display/fonts.py).

get_font() used to construct a brand-new pygame.font.Font on every call
-- fine when called once per screen at startup, but several draw() paths
(nav.py's breadcrumb/footer buttons, app.py's map attribution) call it on
every single frame. Re-parsing a TTF file 30 times a second is wasted
CPU on a Pi4 that's meant to run continuously.
"""

import pygame
import pytest

from flugradar.display import fonts


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((100, 100))
    pygame.font.init()
    yield
    pygame.quit()


class TestFontCaching:
    def test_same_args_return_the_same_font_object(self):
        a = fonts.get_font(14)
        b = fonts.get_font(14)
        assert a is b

    def test_different_size_returns_different_object(self):
        a = fonts.get_font(14)
        b = fonts.get_font(16)
        assert a is not b

    def test_bold_and_regular_are_cached_separately(self):
        a = fonts.get_font(14, bold=False)
        b = fonts.get_font(14, bold=True)
        assert a is not b

    def test_mono_and_regular_are_cached_separately(self):
        a = fonts.get_font(14, mono=False)
        b = fonts.get_font(14, mono=True)
        assert a is not b

    def test_repeated_calls_do_not_grow_the_cache(self):
        for _ in range(50):
            fonts.get_font(14, bold=True, mono=True)
        assert len(fonts._font_cache) == 1

    def test_reset_cache_clears_everything(self):
        fonts.get_font(14)
        assert fonts._font_cache
        fonts.reset_cache()
        assert fonts._font_cache == {}
        assert fonts._resolved is None
        assert fonts._resolved_mono is None

    def test_cache_key_space_stays_small_across_typical_usage(self):
        # The 4 TOKENS font sizes x {bold, plain} x {mono, plain} is the
        # realistic upper bound of distinct fonts an active session uses.
        for size in (7, 9, 11, 14):
            for bold in (False, True):
                for mono in (False, True):
                    fonts.get_font(size, bold=bold, mono=mono)
        assert len(fonts._font_cache) <= 16

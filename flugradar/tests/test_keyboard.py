"""Tests for the on-screen keyboard (flugradar/display/keyboard.py)."""

import pygame
import pytest

from flugradar.display import scaling
from flugradar.display.keyboard import OnScreenKeyboard
from flugradar.display.theme import CLASSIC_AMBER


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    scaling.init(300)
    yield
    pygame.quit()


@pytest.fixture
def kb():
    keyboard = OnScreenKeyboard(300, CLASSIC_AMBER)
    surf = pygame.Surface((300, 300))
    keyboard.draw(surf)  # populate _key_rects
    return keyboard, surf


def _tap_key(kb_obj, surf, key):
    kb_obj.draw(surf)
    for rect, k in kb_obj._key_rects:
        if k == key:
            return kb_obj.handle_tap(rect.centerx, rect.centery)
    raise AssertionError(f"key {key!r} not found (have: {[k for _, k in kb_obj._key_rects]})")


class TestTextEntry:
    def test_tapping_letters_appends_to_text(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "q")
        _tap_key(keyboard, surf, "w")
        assert keyboard.text == "qw"

    def test_backspace_removes_last_char(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "q")
        _tap_key(keyboard, surf, "w")
        _tap_key(keyboard, surf, "back")
        assert keyboard.text == "q"

    def test_backspace_on_empty_text_does_not_crash(self, kb):
        keyboard, surf = kb
        result = _tap_key(keyboard, surf, "back")
        assert result == ""
        assert keyboard.text == ""

    def test_space_appends_a_space(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "q")
        _tap_key(keyboard, surf, "space")
        _tap_key(keyboard, surf, "w")
        assert keyboard.text == "q w"

    def test_ok_returns_ok_without_clearing_text(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "q")
        result = _tap_key(keyboard, surf, "ok")
        assert result == "ok"
        assert keyboard.text == "q"

    def test_reset_clears_text_and_layers(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "q")
        _tap_key(keyboard, surf, "shift")
        keyboard.reset()
        assert keyboard.text == ""
        assert keyboard._shift is False
        assert keyboard._symbols is False


class TestShiftAndSymbolLayers:
    def test_shift_capitalises_next_letter_only(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "shift")
        # once shift is active the row itself renders (and hit-tests)
        # uppercase keys -- "Q", not "q"
        _tap_key(keyboard, surf, "Q")
        assert keyboard.text == "Q"
        assert keyboard._shift is False  # one-shot, like a phone keyboard
        _tap_key(keyboard, surf, "w")
        assert keyboard.text == "Qw"

    def test_symbols_layer_shows_digits(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "123")
        keyboard.draw(surf)
        keys = [k for _, k in keyboard._key_rects]
        assert "1" in keys
        assert "q" not in keys

    def test_abc_returns_to_letters(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "123")
        _tap_key(keyboard, surf, "ABC")
        keyboard.draw(surf)
        keys = [k for _, k in keyboard._key_rects]
        assert "q" in keys

    def test_typing_a_digit_from_symbols_layer(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "123")
        _tap_key(keyboard, surf, "1")
        _tap_key(keyboard, surf, "2")
        assert keyboard.text == "12"

    def test_symbols_layer_has_no_shift_key(self, kb):
        keyboard, surf = kb
        _tap_key(keyboard, surf, "123")
        keyboard.draw(surf)
        keys = [k for _, k in keyboard._key_rects]
        assert "shift" not in keys
        assert "ABC" in keys


class TestLayout:
    def test_all_rows_fit_within_circle_at_their_row(self, kb):
        """Every key rect must stay within the visible circle's chord at
        its own row -- a fixed pixel width would get clipped near the
        top/bottom of a round panel."""
        keyboard, surf = kb
        for rect, _key in keyboard._key_rects:
            hw = scaling.circle_half_width_at_row(rect.y, rect.height)
            cx = scaling.center_x()
            assert rect.left >= cx - hw - scaling.s(2)
            assert rect.right <= cx + hw + scaling.s(2)

    def test_bottom_y_accounts_for_all_four_rows(self, kb):
        keyboard, surf = kb
        assert keyboard.bottom_y() > keyboard.top_y()

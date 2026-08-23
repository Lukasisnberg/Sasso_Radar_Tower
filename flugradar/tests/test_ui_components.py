"""Unit tests for the Schritt-2 UI component layer (flugradar/display/ui/)."""

import pygame
import pytest

from flugradar.display import nav, scaling
from flugradar.display.theme import CLASSIC_AMBER, TOKENS
from flugradar.display.ui import scroll as ui_scroll
from flugradar.display.ui import tap_feedback as tap_feedback_mod
from flugradar.display.ui.button import Button
from flugradar.display.ui.controls import Confirm, Segmented, Slider, Toggle
from flugradar.display.ui.header import Header
from flugradar.display.ui.list_row import ListRow
from flugradar.display.ui.tap_feedback import TapFeedback


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((720, 720))
    scaling.init(720)
    yield
    pygame.quit()


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(tap_feedback_mod.time, "monotonic", fake)
    return fake


class TestTapFeedback:
    def test_no_trigger_is_zero(self):
        assert TapFeedback().brightness() == 0.0

    def test_trigger_is_bright_immediately(self, clock):
        fb = TapFeedback()
        fb.trigger()
        assert fb.brightness() > 0.9

    def test_fades_to_zero_after_duration(self, clock):
        fb = TapFeedback()
        fb.trigger()
        clock.advance(TOKENS.duration_short_ms / 1000.0 + 0.01)
        assert fb.brightness() == 0.0

    def test_partway_is_strictly_between(self, clock):
        fb = TapFeedback()
        fb.trigger()
        clock.advance(TOKENS.duration_short_ms / 1000.0 / 2)
        assert 0.0 < fb.brightness() < 1.0


class TestHeader:
    def test_back_hit_rect_is_tappable(self):
        surface = pygame.Surface((720, 720))
        header = Header(CLASSIC_AMBER)
        header.draw(surface, "Einstellungen", show_back=True)
        assert header._back_rect.width > 0
        assert header.handle_tap(*header._back_rect.center) is True

    def test_no_back_means_no_hit_rect(self):
        surface = pygame.Surface((720, 720))
        header = Header(CLASSIC_AMBER)
        header.draw(surface, "Radar", show_back=False)
        assert header._back_rect.width == 0
        assert header.handle_tap(360, 360) is False

    def test_tap_outside_misses(self):
        surface = pygame.Surface((720, 720))
        header = Header(CLASSIC_AMBER)
        header.draw(surface, "Menu", show_back=True)
        assert header.handle_tap(0, 0) is False


class TestListRow:
    def test_draw_with_every_option_does_not_crash(self):
        surface = pygame.Surface((720, 720))
        row = ListRow(CLASSIC_AMBER)
        row.draw(surface, 300, "Karte", value="CARTO Dark", icon="radar", chevron=True)

    def test_tap_inside_row_hits(self):
        surface = pygame.Surface((720, 720))
        row = ListRow(CLASSIC_AMBER)
        row.draw(surface, 300, "Karte", value="CARTO Dark")
        assert row.handle_tap(*row._rect.center) is True

    def test_tap_outside_row_misses(self):
        surface = pygame.Surface((720, 720))
        row = ListRow(CLASSIC_AMBER)
        row.draw(surface, 300, "Karte")
        assert row.handle_tap(0, 0) is False

    def test_height_matches_touch_target_token(self):
        assert ListRow.height() == scaling.s(TOKENS.touch_target)


class TestToggle:
    def test_tap_inside_hits(self):
        surface = pygame.Surface((720, 720))
        toggle = Toggle(CLASSIC_AMBER)
        toggle.draw(surface, (360, 360), value=True)
        assert toggle.handle_tap(360, 360) is True

    def test_tap_outside_misses(self):
        surface = pygame.Surface((720, 720))
        toggle = Toggle(CLASSIC_AMBER)
        toggle.draw(surface, (360, 360), value=False)
        assert toggle.handle_tap(0, 0) is False


class TestSegmented:
    def test_options_get_distinct_left_to_right_rects(self):
        surface = pygame.Surface((720, 720))
        seg = Segmented(CLASSIC_AMBER)
        seg.draw(surface, pygame.Rect(200, 300, 300, 40), ["km", "sm", "nm"], selected_index=0)
        assert len(seg._option_rects) == 3
        lefts = [r.left for r in seg._option_rects]
        assert lefts == sorted(lefts)

    def test_tap_selects_correct_index(self):
        surface = pygame.Surface((720, 720))
        seg = Segmented(CLASSIC_AMBER)
        seg.draw(surface, pygame.Rect(200, 300, 300, 40), ["km", "sm", "nm"], selected_index=0)
        last_rect = seg._option_rects[-1]
        assert seg.handle_tap(*last_rect.center) == 2

    def test_tap_outside_returns_none(self):
        surface = pygame.Surface((720, 720))
        seg = Segmented(CLASSIC_AMBER)
        seg.draw(surface, pygame.Rect(200, 300, 300, 40), ["km", "sm"], selected_index=0)
        assert seg.handle_tap(0, 0) is None

    def test_empty_options_does_not_crash(self):
        surface = pygame.Surface((720, 720))
        seg = Segmented(CLASSIC_AMBER)
        seg.draw(surface, pygame.Rect(200, 300, 300, 40), [], selected_index=0)
        assert seg._option_rects == []


class TestSlider:
    def test_tap_returns_fraction_along_track(self):
        surface = pygame.Surface((720, 720))
        slider = Slider(CLASSIC_AMBER)
        slider.draw(surface, x0=100, x1=300, y=360, fraction=0.5)
        frac = slider.handle_tap(200, 360)
        assert frac is not None
        assert 0.0 <= frac <= 1.0

    def test_tap_at_left_edge_is_near_zero(self):
        surface = pygame.Surface((720, 720))
        slider = Slider(CLASSIC_AMBER)
        slider.draw(surface, x0=100, x1=300, y=360, fraction=0.5)
        assert slider.handle_tap(100, 360) == pytest.approx(0.0, abs=0.05)

    def test_tap_outside_returns_none(self):
        surface = pygame.Surface((720, 720))
        slider = Slider(CLASSIC_AMBER)
        slider.draw(surface, x0=100, x1=300, y=360, fraction=0.5)
        assert slider.handle_tap(200, 0) is None

    def test_out_of_range_fraction_does_not_crash(self):
        surface = pygame.Surface((720, 720))
        slider = Slider(CLASSIC_AMBER)
        slider.draw(surface, x0=100, x1=300, y=360, fraction=5.0)


class TestConfirm:
    def test_tap_confirm_side(self):
        surface = pygame.Surface((720, 720))
        confirm = Confirm(CLASSIC_AMBER)
        confirm.draw(surface, pygame.Rect(100, 300, 400, 40))
        assert confirm.handle_tap(*confirm._confirm_rect.center) == "confirm"

    def test_tap_cancel_side(self):
        surface = pygame.Surface((720, 720))
        confirm = Confirm(CLASSIC_AMBER)
        confirm.draw(surface, pygame.Rect(100, 300, 400, 40))
        assert confirm.handle_tap(*confirm._cancel_rect.center) == "cancel"

    def test_tap_outside_returns_none(self):
        surface = pygame.Surface((720, 720))
        confirm = Confirm(CLASSIC_AMBER)
        confirm.draw(surface, pygame.Rect(100, 300, 400, 40))
        assert confirm.handle_tap(0, 0) is None

    def test_with_hint_lines_does_not_crash(self):
        surface = pygame.Surface((720, 720))
        confirm = Confirm(CLASSIC_AMBER)
        confirm.draw(surface, pygame.Rect(100, 300, 400, 60), hint_lines=["Trennt aktuelle WLAN-Verbindung."])


class TestButton:
    @pytest.mark.parametrize("variant", ["flat", "filled"])
    def test_draw_both_variants_does_not_crash(self, variant):
        surface = pygame.Surface((720, 720))
        btn = Button(CLASSIC_AMBER, variant=variant)
        btn.draw(surface, pygame.Rect(100, 600, 100, 40), "radar", "RADAR", accent=True)

    def test_unknown_variant_rejected(self):
        with pytest.raises(ValueError):
            Button(CLASSIC_AMBER, variant="bogus")

    def test_tap_inside_hits(self):
        surface = pygame.Surface((720, 720))
        btn = Button(CLASSIC_AMBER)
        rect = pygame.Rect(100, 600, 100, 40)
        btn.draw(surface, rect, "radar", "RADAR")
        assert btn.handle_tap(*rect.center) is True

    def test_tap_outside_misses(self):
        surface = pygame.Surface((720, 720))
        btn = Button(CLASSIC_AMBER)
        rect = pygame.Rect(100, 600, 100, 40)
        btn.draw(surface, rect, "radar", "RADAR")
        assert btn.handle_tap(0, 0) is False


class TestScrollFunctions:
    def test_page_dots_skips_single_page_without_crash(self):
        surface = pygame.Surface((720, 720))
        ui_scroll.draw_page_dots(surface, 0, 1, CLASSIC_AMBER, y=100)

    def test_page_dots_draws_multiple_pages_without_crash(self):
        surface = pygame.Surface((720, 720))
        ui_scroll.draw_page_dots(surface, 1, 3, CLASSIC_AMBER, y=100)

    def test_scroll_arc_skips_when_nothing_overflows(self):
        surface = pygame.Surface((720, 720))
        ui_scroll.draw_scroll_arc(surface, CLASSIC_AMBER, 0, 0, 400)

    def test_scroll_arc_draws_when_overflowing(self):
        surface = pygame.Surface((720, 720))
        ui_scroll.draw_scroll_arc(surface, CLASSIC_AMBER, 50, 200, 400)


class TestNavFooterButtonsUseComponents:
    """nav.py is Schritt 2's first consumer/hardening pass -- its footer
    buttons and page dots must actually go through the new components."""

    def setup_method(self):
        nav._footer_buttons.clear()

    def test_draw_footer_buttons_populates_button_instances(self):
        surface = pygame.Surface((720, 720))
        nav.draw_footer_buttons(surface, ["prev", "next", "radar"], CLASSIC_AMBER)
        assert len(nav._footer_buttons) == 3
        assert all(isinstance(b, Button) for b in nav._footer_buttons)

    def test_tap_triggers_the_matched_button_feedback(self):
        surface = pygame.Surface((720, 720))
        nav.draw_footer_buttons(surface, ["radar"], CLASSIC_AMBER)
        rect = nav.footer_button_rects(1)[0]
        idx = nav.tap_footer_button(rect.centerx, rect.centery, 1)
        assert idx == 0
        assert nav._footer_buttons[0]._feedback.brightness() > 0

    def test_tap_outside_any_button_returns_none(self):
        surface = pygame.Surface((720, 720))
        nav.draw_footer_buttons(surface, ["radar"], CLASSIC_AMBER)
        assert nav.tap_footer_button(0, 0, 1) is None

    def test_page_dots_still_callable_with_original_signature(self):
        # detail.py calls this directly -- must keep working unchanged.
        surface = pygame.Surface((720, 720))
        nav.draw_page_dots(surface, 0, 3, CLASSIC_AMBER)

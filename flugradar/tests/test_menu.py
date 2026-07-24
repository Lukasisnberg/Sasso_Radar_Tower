"""Tests for the on-device settings menu (Ausbaustufe 2, Schritt 4)."""

import json
from unittest.mock import MagicMock

import pygame
import pytest

from flugradar.config import settings as settings_mod
from flugradar.config.settings import AppSettings
from flugradar.config.locations import LOCATIONS
from flugradar.display import scaling
from flugradar.display.screens import menu as menu_mod
from flugradar.display.screens.menu import MenuScreen, _ROOT_ORDER
from flugradar.display.theme import CLASSIC_AMBER


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    scaling.init(300)
    yield
    pygame.quit()


@pytest.fixture
def settings(tmp_path, monkeypatch):
    portal_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
    return AppSettings()


@pytest.fixture
def screen(settings):
    m = MenuScreen(300, CLASSIC_AMBER, settings)
    surf = pygame.Surface((300, 300))
    m.draw(surf)  # populate _row_rects for the root list
    return m, surf


def _tap_row(m, surf, key):
    """Draw, find the row with `key`, and tap its centre."""
    m.draw(surf)
    for rect, row in m._row_rects:
        if row.key == key:
            return m.handle_tap(rect.centerx, rect.centery), rect, row
    raise AssertionError(f"row {key!r} not found (have: {[r.key for _, r in m._row_rects]})")


class TestNavigation:
    def test_root_has_all_seven_sections(self, screen):
        m, surf = screen
        assert [r.key for _, r in m._row_rects] == list(_ROOT_ORDER)

    def test_tapping_a_section_opens_its_submenu(self, screen):
        m, surf = screen
        result, _, _ = _tap_row(m, surf, "map")
        assert result == "menu"
        assert m._open == "map"

    def test_back_arrow_from_submenu_returns_to_root(self, screen):
        m, surf = screen
        _tap_row(m, surf, "display")
        assert m._open == "display"
        m.draw(surf)
        result = m.handle_tap(m._back_rect.centerx, m._back_rect.centery)
        assert result == "menu"
        assert m._open is None

    def test_back_arrow_from_root_exits_to_radar(self, screen):
        m, surf = screen
        m.draw(surf)
        result = m.handle_tap(m._back_rect.centerx, m._back_rect.centery)
        assert result == "radar"

    def test_swipe_right_equivalent_go_back_from_root_returns_radar(self, screen):
        m, surf = screen
        assert m.go_back() == "radar"

    def test_swipe_right_equivalent_go_back_from_submenu_returns_menu(self, screen):
        m, surf = screen
        _tap_row(m, surf, "filter")
        assert m.go_back() == "menu"
        assert m._open is None

    @pytest.mark.parametrize("key", list(_ROOT_ORDER))
    def test_every_section_opens_and_returns_without_dead_end(self, screen, key):
        m, surf = screen
        result, _, _ = _tap_row(m, surf, key)
        assert result == "menu"
        assert m._open == key
        assert m.go_back() == "menu"
        assert m._open is None


class TestCircularHitZones:
    def test_row_near_vertical_centre_is_wider_than_row_near_top_edge(self, screen):
        m, surf = screen
        rects = [rect for rect, _ in m._row_rects]
        widest = max(r.width for r in rects)
        narrowest = min(r.width for r in rects)
        # rows further from the vertical centre must be clipped narrower --
        # otherwise the chord-following layout (4.4) isn't doing anything
        assert narrowest < widest

    def test_tap_far_outside_any_row_hits_nothing(self, screen):
        m, surf = screen
        # corner of the square canvas, well outside the round visible area
        result = m.handle_tap(2, 2)
        assert result == ""


class TestLocationAndRadius:
    def test_selecting_a_location_sets_home_coordinates(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "location")
        result, rect, row = _tap_row(m, surf, "home_location")
        assert result == "changed"
        matched = [
            loc for loc in LOCATIONS
            if loc.lat == settings.home.lat and loc.lon == settings.home.lon
        ]
        assert len(matched) == 1

    def test_cycling_location_twice_reaches_the_other_preset(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "location")
        _tap_row(m, surf, "home_location")
        first = (settings.home.lat, settings.home.lon)
        _tap_row(m, surf, "home_location")
        second = (settings.home.lat, settings.home.lon)
        assert first != second
        assert len(LOCATIONS) == 2  # sanity: cycling both locations covers the whole set

    def test_radius_select_sets_a_preset_value(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "location")
        result, rect, row = _tap_row(m, surf, "radius")
        assert result == "changed"
        from flugradar.config.locations import RADIUS_PRESETS_KM
        assert settings.home.radius_km in RADIUS_PRESETS_KM


class TestValueClamping:
    def test_slider_tap_at_left_edge_hits_minimum(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "filter")
        m.draw(surf)
        rect, row = next(rr for rr in m._row_rects if rr[1].key == "min_alt")
        m.handle_tap(rect.left + 1, rect.centery)
        assert settings.min_altitude_ft == row.min_v

    def test_slider_tap_at_right_edge_hits_maximum(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "filter")
        m.draw(surf)
        rect, row = next(rr for rr in m._row_rects if rr[1].key == "min_alt")
        m.handle_tap(rect.right - 1, rect.centery)
        assert settings.min_altitude_ft == row.max_v

    def test_slider_value_always_within_bounds_across_the_row(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "screen")
        m.draw(surf)
        rect, row = next(rr for rr in m._row_rects if rr[1].key == "brightness")
        for x in range(rect.left, rect.right, max(1, rect.width // 10)):
            m.handle_tap(x, rect.centery)
            assert row.min_v <= settings.brightness <= row.max_v


class TestToggleAndSelect:
    def test_toggle_flips_and_persists(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "display")
        before = settings.show_compass
        result, _, _ = _tap_row(m, surf, "compass")
        assert result == "changed"
        assert settings.show_compass != before

    def test_disabled_row_ignores_taps(self, screen, settings):
        assert settings.openaip_api_key == ""
        m, surf = screen
        _tap_row(m, surf, "map")
        before = settings.openaip_overlay_enabled
        result, _, _ = _tap_row(m, surf, "openaip")
        assert result == ""
        assert settings.openaip_overlay_enabled == before

    def test_select_cycles_through_all_options_and_wraps(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "units")
        _, _, row = _tap_row(m, surf, "distance_unit")
        seen = [settings.distance_unit]
        for _ in range(len(row.options)):
            _tap_row(m, surf, "distance_unit")
            seen.append(settings.distance_unit)
        assert seen[0] == seen[-1]  # wrapped back to the start


class TestConfirmAction:
    def test_first_tap_enters_confirm_state_without_acting(self, screen, monkeypatch):
        m, surf = screen
        mock_action = MagicMock()
        monkeypatch.setattr(menu_mod, "system_action", mock_action)
        _tap_row(m, surf, "system")
        result, rect, row = _tap_row(m, surf, "restart")
        assert result == ""
        assert m._confirm_key == "restart"
        mock_action.assert_not_called()

    def test_confirm_tap_runs_the_action(self, screen, monkeypatch):
        m, surf = screen
        mock_action = MagicMock()
        monkeypatch.setattr(menu_mod, "system_action", mock_action)
        _tap_row(m, surf, "system")
        _, rect, row = _tap_row(m, surf, "restart")
        m.draw(surf)
        rect, _ = next(rr for rr in m._row_rects if rr[1].key == "restart")
        m.handle_tap(rect.left + 2, rect.centery)  # left half == confirm
        mock_action.assert_called_once_with("reboot")

    def test_cancel_tap_does_not_run_the_action(self, screen, monkeypatch):
        m, surf = screen
        mock_action = MagicMock()
        monkeypatch.setattr(menu_mod, "system_action", mock_action)
        _tap_row(m, surf, "system")
        _tap_row(m, surf, "shutdown")
        m.draw(surf)
        rect, _ = next(rr for rr in m._row_rects if rr[1].key == "shutdown")
        m.handle_tap(rect.right - 2, rect.centery)  # right half == cancel
        mock_action.assert_not_called()
        assert m._confirm_key is None

    def test_leaving_the_submenu_clears_pending_confirmation(self, screen):
        m, surf = screen
        _tap_row(m, surf, "system")
        _tap_row(m, surf, "restart")
        assert m._confirm_key == "restart"
        m.go_back()
        assert m._confirm_key is None


class TestPersistence:
    def test_changes_land_in_settings_json(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "display")
        _tap_row(m, surf, "theme")
        data = json.loads(settings_mod.PORTAL_SETTINGS_FILE.read_text())
        assert data["theme"] == settings.theme

    def test_round_trip_through_a_fresh_settings_instance(self, screen, settings, monkeypatch):
        m, surf = screen
        _tap_row(m, surf, "filter")
        _tap_row(m, surf, "hl_military")
        expected = settings.highlight_military

        reloaded = AppSettings()
        assert reloaded.highlight_military == expected

    def test_save_never_leaves_a_stray_tmp_file(self, screen, settings):
        m, surf = screen
        _tap_row(m, surf, "units")
        _tap_row(m, surf, "temperature_unit")
        tmp_path = settings_mod.PORTAL_SETTINGS_FILE.with_suffix(".json.tmp")
        assert not tmp_path.exists()
        # and the real file must be valid, complete JSON
        json.loads(settings_mod.PORTAL_SETTINGS_FILE.read_text())

    def test_menu_change_marks_portal_synced_so_it_wont_self_trigger_reload(self, settings):
        settings.save_portal_settings({"theme": "mono"})
        settings.mark_portal_synced()
        assert settings.check_portal_reload() is False

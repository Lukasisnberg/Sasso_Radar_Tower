"""Tests for the web portal's design system (docs/prompt-portal-design.md):
CSS tokens must stay byte-for-byte in sync with theme.py's CLASSIC_AMBER
hex values, fonts must be vendored locally with a working fallback
chain, and pages must render regardless of whether settings are at
their defaults or explicitly set.
"""

import re
from pathlib import Path

import pytest

from flugradar.config import settings as settings_mod
from flugradar.config.settings import AppSettings
from flugradar.display.theme import CLASSIC_AMBER
from flugradar.web.app import create_app

_STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
_CSS_PATH = _STATIC_DIR / "style.css"
_FONTS_DIR = _STATIC_DIR / "fonts"


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


@pytest.fixture()
def client(monkeypatch, tmp_path):
    portal_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
    settings = AppSettings()
    app = create_app(settings)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestColourTokensMatchDevice:
    """The whole point of the redesign: portal and device panel use the
    exact same colours. If theme.py's CLASSIC_AMBER values ever change,
    this must fail rather than silently drift out of sync."""

    @pytest.fixture(autouse=True)
    def css_text(self):
        self.css = _CSS_PATH.read_text()

    def test_background_matches_theme(self):
        assert _hex(CLASSIC_AMBER.background) in self.css

    def test_primary_text_matches_theme_label(self):
        assert _hex(CLASSIC_AMBER.label) in self.css

    def test_muted_text_matches_theme_muted(self):
        assert _hex(CLASSIC_AMBER.muted) in self.css

    def test_hint_text_matches_theme_hint(self):
        assert _hex(CLASSIC_AMBER.hint) in self.css

    def test_accent_matches_theme_sweep_colour(self):
        assert _hex(CLASSIC_AMBER.sweep_colour) in self.css

    def test_danger_matches_theme_emergency(self):
        assert _hex(CLASSIC_AMBER.emergency) in self.css


class TestFontSetup:
    def test_regular_weight_file_present_on_disk(self):
        assert (_FONTS_DIR / "Inter-Regular.woff2").is_file()

    def test_semibold_weight_file_present_on_disk(self):
        assert (_FONTS_DIR / "Inter-SemiBold.woff2").is_file()

    def test_license_file_present(self):
        assert (_FONTS_DIR / "LICENSE.txt").is_file()
        text = (_FONTS_DIR / "LICENSE.txt").read_text()
        assert "SIL Open Font License" in text

    def test_font_files_served_by_flask(self, client):
        assert client.get("/static/fonts/Inter-Regular.woff2").status_code == 200
        assert client.get("/static/fonts/Inter-SemiBold.woff2").status_code == 200

    def test_font_face_declares_both_weights(self):
        css = _CSS_PATH.read_text()
        assert "@font-face" in css
        assert "Inter-Regular.woff2" in css
        assert "Inter-SemiBold.woff2" in css

    def test_body_has_a_multi_font_fallback_chain(self):
        css = _CSS_PATH.read_text()
        match = re.search(r"body\s*\{[^}]*font-family:\s*([^;]+);", css)
        assert match, "body { font-family: ... } not found in style.css"
        family_list = match.group(1)
        assert "Inter" in family_list
        # A real fallback chain, not just Inter alone -- if the vendored
        # file is ever missing, the browser still has somewhere to fall
        # through to instead of the page looking broken.
        assert family_list.count(",") >= 2

    def test_missing_font_files_do_not_break_page_rendering(self, client, tmp_path):
        # Really move the font files aside (not just mock a check) --
        # the route itself never touches them, only the stylesheet
        # references them via @font-face, so pages must render exactly
        # the same regardless. Restored in `finally` either way.
        import shutil
        backup = tmp_path / "fonts_backup"
        shutil.move(str(_FONTS_DIR), str(backup))
        try:
            r = client.get("/")
            assert r.status_code == 200
        finally:
            shutil.move(str(backup), str(_FONTS_DIR))


class TestPagesRenderWithDefaultAndSetValues:
    def test_dashboard_renders_with_default_settings(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Sasso Radar Tower" in r.data

    def test_dashboard_renders_after_settings_are_saved(self, client):
        client.post("/radar", data={"home_lat": "48.8566", "home_lon": "2.3522"})
        r = client.get("/")
        assert r.status_code == 200
        assert b"48.8566" in r.data

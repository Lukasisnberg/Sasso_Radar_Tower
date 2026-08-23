"""Ausbaustufe 2, Schritt 3 (docs/prompt-ausbaustufe-2.md) -- polish pass.

Two checks the step's own test list asks for:
- No module outside the token module (theme.py) hardcodes a colour tuple.
- A missing/unresolvable font falls back cleanly instead of crashing.
"""

import pathlib
import re

import pygame
import pytest

DISPLAY_DIR = pathlib.Path(__file__).resolve().parent.parent / "display"

_COLOR_TUPLE_RE = re.compile(
    r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*\d{1,3}\s*)?\)"
)

# (relative path, exact stripped line) pairs that legitimately contain a
# digit-tuple outside theme.py -- not a design/colour decision, so exempt
# from the "colours live in theme.py" rule:
_ALLOWED = {
    ("display/renderer.py", "for deg in range(0, 360, 10):"),  # compass degrees, not a colour
    ("display/renderer.py", "self._sweep_surface.fill((0, 0, 0, 0))"),  # clear scratch surface to transparent
    ("display/renderer.py", "scratch.fill((0, 0, 0, 0))"),  # clear scratch surface to transparent
    ("display/mask.py", "mask.fill((0, 0, 0, 255))"),  # opaque stencil, only valid value
    ("display/screens/menu.py", "self._back_rect = pygame.Rect(0, 0, 0, 0)"),  # rect geometry, not a colour
    # Same rect-geometry-not-a-colour reasoning as the menu.py line above --
    # pre-existing gap in this allowlist found while touching wifi.py for
    # Schritt 1 of the UI overhaul (the WLAN screen was added after this
    # allowlist was last updated, so test_no_stray_color_tuples would
    # already fail on unmodified `main` for these three lines).
    ("display/screens/wifi.py", "self._back_rect = pygame.Rect(0, 0, 0, 0)"),
    ("display/screens/wifi.py", "self._reload_rect = pygame.Rect(0, 0, 0, 0)"),
    ("display/screens/wifi.py", "self._eye_rect = pygame.Rect(0, 0, 0, 0)"),
    ("display/mask.py", "pygame.draw.circle(mask, (0, 0, 0, 0), (size // 2, size // 2), size // 2)"),  # transparent punch
    ("display/aircraft_icons.py", 'tinted.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)'),  # tint-recipe constant, not a colour choice
    ("display/weather_icons.py", 'tinted.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)'),  # tint-recipe constant, not a colour choice
    ("display/ui_icons.py", 'tinted.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)'),  # tint-recipe constant, not a colour choice
}


def _display_py_files():
    return [p for p in DISPLAY_DIR.rglob("*.py") if p.name != "theme.py"]


class TestNoHardcodedColorsOutsideTheme:
    def test_no_stray_color_tuples(self):
        offenders = []
        for path in _display_py_files():
            # .as_posix(), not str() -- on Windows, relative_to() yields
            # backslash-separated paths, which would never match _ALLOWED's
            # forward-slash keys (silently failing every entry, not just
            # newly added ones).
            rel = path.relative_to(DISPLAY_DIR.parent).as_posix()
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not _COLOR_TUPLE_RE.search(line):
                    continue
                if (rel, line.strip()) in _ALLOWED:
                    continue
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
        assert not offenders, "hardcoded colour tuple(s) outside theme.py:\n" + "\n".join(offenders)


class TestFontFallback:
    @pytest.fixture(autouse=True)
    def init_pygame(self):
        pygame.init()
        yield
        pygame.quit()

    def test_missing_family_falls_back_without_crash(self, monkeypatch):
        from flugradar.display import fonts

        monkeypatch.setattr(fonts, "_resolved", None)
        monkeypatch.setattr(fonts, "_resolved_mono", None)
        monkeypatch.setattr(pygame.font, "get_fonts", lambda: [])

        font = fonts.get_font(12)
        assert isinstance(font, pygame.font.Font)

    def test_missing_mono_family_falls_back_without_crash(self, monkeypatch):
        from flugradar.display import fonts

        monkeypatch.setattr(fonts, "_resolved", None)
        monkeypatch.setattr(fonts, "_resolved_mono", None)
        monkeypatch.setattr(pygame.font, "get_fonts", lambda: [])

        font = fonts.get_font(12, mono=True)
        assert isinstance(font, pygame.font.Font)

    def test_resolve_family_prefers_first_available(self, monkeypatch):
        from flugradar.display import fonts

        families = ("Inter", "IBM Plex Sans", "DejaVu Sans", "sans")
        # pygame.font.get_fonts() returns lowercase, space-stripped names.
        monkeypatch.setattr(pygame.font, "get_fonts", lambda: ["dejavusans", "sans"])
        assert fonts._resolve_family(families) == "DejaVu Sans"

    def test_resolve_family_falls_back_to_last_when_none_available(self):
        from flugradar.display.fonts import _resolve_family

        families = ("Inter", "IBM Plex Sans", "sans")
        assert _resolve_family(families) == "sans"

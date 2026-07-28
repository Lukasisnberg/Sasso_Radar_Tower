#!/usr/bin/env python3
"""Generate the boot splash logo (radar circle) and colour-matched
Plymouth script from the current design tokens.

Run by install.sh on every (re-)install:
    python3 generate_logo.py <logo.png> <sasso-radar.script> [settings.json]

Reads the theme (amber/mono) the user last picked via the device menu/
portal from the same settings.json flugradar/config/settings.py writes, so
the boot splash matches whatever's actually configured instead of always
showing the default. `settings.json` is optional -- omit it (or point it
at a file that doesn't exist) to fall back to amber, same as
resolve_theme() does for a missing/unknown theme name at runtime.

This script runs under the system python3 (not the project's venv --
Plymouth theme generation happens during `sudo bash install.sh`, before/
outside of any venv), so it can't rely on `pip install -e .` having made
`flugradar` importable. It adds the repo root to sys.path itself and
imports flugradar.display.theme directly instead of duplicating its
colour constants -- theme.py has no dependencies beyond the standard
library (no pygame import), so this works even without the project's
Python dependencies installed. If that import ever fails for some
unforeseen reason, a small hardcoded fallback (the current amber values)
keeps this script from hard-erroring out of an install.
"""

import json
import math
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

try:
    from flugradar.display.theme import CLASSIC_AMBER, MONO
    _THEMES = {"amber": CLASSIC_AMBER, "mono": MONO}
except Exception:  # pragma: no cover -- see module docstring
    _THEMES = {}

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Pillow not installed -- skipping logo image generation.", file=sys.stderr)

SIZE = 200
CENTER = SIZE // 2
RADIUS = 80

_SCRIPT_TEMPLATE = Path(__file__).with_name("sasso-radar.script.tmpl")


def _resolve_theme_name(settings_path: Path) -> str:
    """Same fallback philosophy as flugradar.display.theme.resolve_theme():
    missing file, unreadable JSON, or an unknown/removed theme name all
    silently fall back to "amber" rather than erroring out an install."""
    try:
        data = json.loads(settings_path.read_text())
    except (OSError, json.JSONDecodeError):
        return "amber"
    name = data.get("theme", "amber")
    return name if name in ("amber", "mono") else "amber"


def _resolve_colours(settings_path: Path):
    if not _THEMES:
        # theme.py import failed -- current amber values, kept in sync by
        # hand as an absolute last resort (see module docstring).
        return {
            "background": (11, 13, 15),
            "accent": (210, 180, 70),
            "ring": (115, 99, 39),
            "muted": (180, 185, 182),
        }
    theme = _THEMES[_resolve_theme_name(settings_path)]
    return {
        "background": theme.background,
        "accent": theme.sweep_colour,
        "ring": theme.radar_ring,
        "muted": theme.muted,
    }


def _draw_logo(out_path: Path, colours: dict) -> None:
    bg = colours["background"]
    ring = colours["ring"]
    accent = colours["accent"]

    img = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(img)

    for r in (RADIUS, RADIUS * 2 // 3, RADIUS // 3):
        draw.ellipse(
            (CENTER - r, CENTER - r, CENTER + r, CENTER + r),
            outline=ring, width=1,
        )

    draw.line((CENTER, CENTER - RADIUS, CENTER, CENTER + RADIUS), fill=ring, width=1)
    draw.line((CENTER - RADIUS, CENTER, CENTER + RADIUS, CENTER), fill=ring, width=1)

    draw.ellipse((CENTER - 3, CENTER - 3, CENTER + 3, CENTER + 3), fill=accent)

    # Frozen sweep trail (fading dots) -- the .script's own live sweep
    # animates on top of this at boot; this static echo of it keeps the
    # very first painted frame (before the script's refresh callback has
    # ticked even once) from looking like a bare, empty radar face.
    for angle_deg in range(0, 45):
        angle = math.radians(angle_deg - 90)
        r = RADIUS * angle_deg / 44
        x = CENTER + int(r * math.cos(angle))
        y = CENTER + int(r * math.sin(angle))
        alpha = angle_deg / 44
        faded = tuple(int(bg[i] + (accent[i] - bg[i]) * alpha) for i in range(3))
        draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=faded)

    img.save(out_path)
    print(f"Wrote {out_path}")


def _write_script(out_path: Path, colours: dict) -> None:
    template = _SCRIPT_TEMPLATE.read_text()
    bg = colours["background"]
    accent = colours["accent"]
    muted = colours["muted"]

    def norm(rgb):
        return tuple(round(c / 255, 4) for c in rgb)

    bg_n, accent_n, muted_n = norm(bg), norm(accent), norm(muted)
    rendered = (
        template
        .replace("{{BG_R}}", str(bg_n[0])).replace("{{BG_G}}", str(bg_n[1])).replace("{{BG_B}}", str(bg_n[2]))
        .replace("{{ACCENT_R}}", str(accent_n[0])).replace("{{ACCENT_G}}", str(accent_n[1])).replace("{{ACCENT_B}}", str(accent_n[2]))
        .replace("{{MUTED_R}}", str(muted_n[0])).replace("{{MUTED_G}}", str(muted_n[1])).replace("{{MUTED_B}}", str(muted_n[2]))
    )
    out_path.write_text(rendered)
    print(f"Wrote {out_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: generate_logo.py <logo.png> <sasso-radar.script> [settings.json]", file=sys.stderr)
        sys.exit(1)
    logo_out = Path(sys.argv[1])
    script_out = Path(sys.argv[2])
    settings_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.home() / ".local" / "share" / "flugradar" / "settings.json"

    colours = _resolve_colours(settings_path)

    if HAS_PIL:
        _draw_logo(logo_out, colours)
    if _SCRIPT_TEMPLATE.exists():
        _write_script(script_out, colours)
    else:
        print(f"Script template {_SCRIPT_TEMPLATE} not found -- skipping.", file=sys.stderr)


if __name__ == "__main__":
    main()

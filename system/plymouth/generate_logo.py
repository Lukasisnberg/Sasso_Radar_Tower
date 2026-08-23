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
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Pillow not installed -- skipping logo image generation.", file=sys.stderr)

SIZE = 200
CENTER = SIZE // 2
RADIUS = 80

TITLE_TEXT = "SASSO RADAR TOWER"
TITLE_FONT_SIZE = 22
TITLE_GAP = 12
TITLE_PADDING = 16

# The FlightPanel enclosure mounts the DSI panel physically rotated 90°
# clockwise -- same fixed hardware fact as `--rotation -90` in
# system/flugradar-display-start.sh. Plymouth runs before flugradar-display
# (no pygame yet to do that compensation itself), so the whole static boot
# graphic (rings + title) is composed unrotated below and rotated once as a
# single image here instead. -90 is deliberately the same value and the
# same rotate() convention as the pygame side: verified empirically that
# PIL.Image.rotate() and pygame.transform.rotate() produce identical pixel
# mappings for exact 90° rotations (both treat negative degrees as
# clockwise) -- see flugradar/display/gestures.py's _rotate_point() for the
# analogous, also-verified touch-coordinate derivation.
BOOT_ROTATION_DEG = -90

_SCRIPT_TEMPLATE = Path(__file__).with_name("sasso-radar.script.tmpl")


def _resolve_font(size: int) -> "ImageFont.ImageFont":
    """Looks up an installed TTF via fontconfig by family name (same
    families flugradar/display/fonts.py falls back through), since PIL
    -- unlike Plymouth's own Image.Text() -- needs an actual font *file*,
    not just a family name. Falls back to PIL's built-in bitmap font
    (small, but never crashes an install) if fontconfig or all three
    families are unavailable."""
    import subprocess
    for family in ("Inter", "DejaVu Sans", "Noto Sans"):
        try:
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", family],
                capture_output=True, text=True, timeout=2,
            )
            path = result.stdout.strip()
            if path:
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


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


def _draw_logo(out_path: Path, colours: dict) -> tuple[float, float]:
    """Draws the rings graphic + title text unrotated (as if the panel
    were mounted normally), composes them into one image, then rotates
    that whole composition once for the physically-rotated FlightPanel
    mount. Returns (dot_offset_x, dot_offset_y): where the rings' own
    centre (the live sweep dot's orbit centre, animated separately by
    the .script at boot) ends up inside the *rotated* saved image --
    the .script positions its dot relative to this, since a circular
    orbit doesn't otherwise need rotating (a circle is rotation-symmetric
    about its own centre; only where that centre sits does)."""
    bg = colours["background"]
    ring = colours["ring"]
    accent = colours["accent"]
    muted = colours["muted"]

    rings = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(rings)

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

    font = _resolve_font(TITLE_FONT_SIZE)
    measurer = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tx0, ty0, tx1, ty1 = measurer.textbbox((0, 0), TITLE_TEXT, font=font)
    title_w, title_h = tx1 - tx0, ty1 - ty0

    canvas_w = max(SIZE, title_w + TITLE_PADDING * 2)
    canvas_h = SIZE + TITLE_GAP + title_h
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg)
    canvas.paste(rings, ((canvas_w - SIZE) // 2, 0))
    ImageDraw.Draw(canvas).text(
        ((canvas_w - title_w) // 2 - tx0, SIZE + TITLE_GAP - ty0),
        TITLE_TEXT, fill=muted, font=font,
    )

    # Where the rings' own centre sits in the unrotated canvas.
    rings_cx, rings_cy = canvas_w / 2, SIZE / 2
    # Same (x, y) -> (H-1-y, x) mapping pygame.transform.rotate(-90) uses
    # (verified against actual pygame/PIL output, not derived on paper --
    # see flugradar/display/gestures.py's _rotate_point()).
    dot_offset = (canvas_h - 1 - rings_cy, rings_cx)

    rotated = canvas.rotate(BOOT_ROTATION_DEG, expand=True)
    rotated.save(out_path)
    print(f"Wrote {out_path}")
    return dot_offset


def _write_script(out_path: Path, colours: dict, dot_offset: tuple[float, float]) -> None:
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
        .replace("{{DOT_OFFSET_X}}", str(dot_offset[0])).replace("{{DOT_OFFSET_Y}}", str(dot_offset[1]))
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

    # Falls back to roughly the rings' own centre (no title-strip offset)
    # if Pillow isn't installed and _draw_logo() never ran -- logo.png
    # itself is skipped in that case too (module docstring), so the
    # .script would fail to load it regardless; this just keeps the
    # template placeholder from being left unsubstituted.
    dot_offset = (SIZE / 2 - 1, SIZE / 2)
    if HAS_PIL:
        dot_offset = _draw_logo(logo_out, colours)
    if _SCRIPT_TEMPLATE.exists():
        _write_script(script_out, colours, dot_offset)
    else:
        print(f"Script template {_SCRIPT_TEMPLATE} not found -- skipping.", file=sys.stderr)


if __name__ == "__main__":
    main()

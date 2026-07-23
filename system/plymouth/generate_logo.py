#!/usr/bin/env python3
"""Generate the boot splash logo (radar circle) as a PNG.

Run once during install: python3 generate_logo.py
Requires PIL/Pillow — installed as part of the system setup.
"""

import math
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow not installed — skipping logo generation.", file=sys.stderr)
    sys.exit(0)

SIZE = 200
CENTER = SIZE // 2
RADIUS = 80
BG = (10, 15, 10)
RING = (0, 80, 0)
CROSS = (0, 120, 0)
DOT = (0, 200, 0)

img = Image.new("RGB", (SIZE, SIZE), BG)
draw = ImageDraw.Draw(img)

for r in (RADIUS, RADIUS * 2 // 3, RADIUS // 3):
    draw.ellipse(
        (CENTER - r, CENTER - r, CENTER + r, CENTER + r),
        outline=RING, width=1,
    )

draw.line((CENTER, CENTER - RADIUS, CENTER, CENTER + RADIUS), fill=CROSS, width=1)
draw.line((CENTER - RADIUS, CENTER, CENTER + RADIUS, CENTER), fill=CROSS, width=1)

draw.ellipse((CENTER - 3, CENTER - 3, CENTER + 3, CENTER + 3), fill=DOT)

for angle_deg in range(0, 45):
    angle = math.radians(angle_deg - 90)
    r = RADIUS * angle_deg / 44
    x = CENTER + int(r * math.cos(angle))
    y = CENTER + int(r * math.sin(angle))
    alpha = int(200 * (angle_deg / 44))
    draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(0, alpha, 0))

out = sys.argv[1] if len(sys.argv) > 1 else "logo.png"
img.save(out)
print(f"Wrote {out}")

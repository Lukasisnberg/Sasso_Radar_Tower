# Source

37 SVG icons downloaded from the free "ADS-B Radar Icons" package at
https://adsb-radar.com/help/icons.html (full-package download link on that
page), retrieved 2026-07-24. License terms: see `LICENSE.txt` in this
directory.

Filenames are unchanged from the downloaded package (already lowercase,
no spaces) except that the enclosing zip folder and the macOS
`__MACOSX`/`.DS_Store` cruft and the bundled `Readme and Attribution.rtf`
were dropped — their content is folded into `LICENSE.txt` instead.

## What each file represents

Two families of icons ship in the source package:

1. **Category icons** — one file per ADS-B/Mode-S emitter category code
   (`a0.svg` … `a7.svg`, `b0.svg` … `b4.svg`, `c0.svg`), used as the
   fallback silhouette when only the coarse `category` field is known.
   Plus three extra fighter-jet variants (`f5.svg`, `f11.svg`, `f15.svg`)
   that the source does not bind to any specific ICAO type code or
   category — they ship as unused bonus assets, not referenced by
   `flugradar/display/icon_mapping.py`.
2. **Type icons** — one file per specific ICAO type designator or family
   (`a320.svg`, `b737.svg`, `cessna.svg`, `glf5.svg`, ... ), each mapped
   from a list of real ICAO type codes given in the source page's
   per-icon tooltip text. This list was scraped programmatically from
   the page (not hand-transcribed) to avoid transcription errors, and
   lives in `flugradar/display/icon_mapping.py` as `TYPE_CODE_TO_ICON`.

## Category → icon mapping

`a0.svg` … `a7.svg` map 1:1 to Mode-S categories A0–A7. `b0.svg` … `b4.svg`
map 1:1 to B0–B4. The source page's own tooltip for `b0.svg` states it
covers categories `B0, B5, B6, B7` (plus a legacy `F13` internal code) —
i.e. the source has **no dedicated icon for B6 (Unmanned Aerial
Vehicle/drone)** or B7 (space vehicle); both fall back to the generic
`b0.svg`/`a0.svg` shape. Per the build instructions, this was **not**
patched in from another source — the drone/UAV category simply renders
as the generic icon. Flagged here as a known gap; a dedicated drone
silhouette would need to be drawn separately if desired later (e.g. the
hand-drawn `_DRONE_HALF` polygon already present in `aircraft_icons.py`'s
"simple" render path could be adapted, but that would mix drawing styles
within the "detailed" icon set, so it hasn't been done).

`c0.svg` (and by extension categories C1–C7, D0–D7, which have no icon at
all in the source set) represents non-aircraft ADS-B emitters (surface
vehicles, obstacles); `flugradar/display/icon_mapping.py` maps all of
those to `c0.svg` since none are relevant to an airborne radar and the
source provides no finer breakdown.

## Attribution

See `LICENSE.txt`. Implemented in README.md, the on-device About screen,
the web portal About page, and `docs/ANFORDERUNGEN.md`.

"""Shared UI-component layer (Schritt 2 of the UI overhaul, docs/ui-inventar.md).

Buttons, list rows, toggles/sliders/segmented controls, the confirm
row, the header, and the scroll chrome (arc/dots) are built once here
and consumed by screens instead of each screen drawing its own controls
from primitives. Every component:

- takes `theme` (a `flugradar.display.theme.Theme`) as a constructor
  argument, stored as a plain mutable attribute so a live theme-reload
  can update it in place, matching every existing screen class;
- reads sizes exclusively from `flugradar.display.theme.TOKENS`, never a
  free literal;
- resolves its own left/right bounds from `scaling.circle_half_width_at_row()`
  where it occupies a row, rather than requiring the caller to compute
  them (Rahmenbedingungen: components respect the chord themselves);
- holds no state of its own beyond animation progress (tap feedback) --
  no reference to `AppSettings` or any screen-level state;
- gives visible tap feedback via `flugradar.display.ui.tap_feedback.TapFeedback`,
  a brief highlight fading over `TOKENS.duration_short_ms`, shared so
  every component's feedback looks and times identically.

`nav.py` is the first consumer (footer buttons, page dots, and the
scroll arc shared between menu.py/wifi.py, which had two copies of the
same function). Screens' own row/control rendering (menu.py's `_draw_row`
and friends) still draws inline -- migrating those onto `ListRow`/
`Toggle`/`Segmented`/`Slider`/`Confirm` is Schritt 4, not this step.
"""

"""Shared tap-feedback state (Schritt 2 of the UI overhaul).

Today's UI gives no acknowledgement that a tap landed -- on a touchscreen
with no haptics, that is the one thing every interactive element needs.
Every component embeds one `TapFeedback` instance so the flash looks and
times identically everywhere: `trigger()` on a tap, `brightness()` read
every frame while drawing to blend the component's fill/text toward its
highlight colour (`theme.blend(base, highlight, brightness())`).
"""

from __future__ import annotations

import time

from flugradar.display.theme import TOKENS, ease_out_cubic


class TapFeedback:
    def __init__(self) -> None:
        self._tapped_at: float | None = None

    def trigger(self) -> None:
        self._tapped_at = time.monotonic()

    def brightness(self) -> float:
        """1.0 right after a tap, eased down to 0.0 over
        TOKENS.duration_short_ms. Returns 0.0 once settled -- also resets
        the internal timer then, so a caller can check `brightness() > 0`
        each frame without ever needing to poll a separate "is animating"
        flag."""
        if self._tapped_at is None:
            return 0.0
        duration = TOKENS.duration_short_ms / 1000.0
        elapsed = time.monotonic() - self._tapped_at
        if elapsed >= duration:
            self._tapped_at = None
            return 0.0
        return 1.0 - ease_out_cubic(elapsed / duration)

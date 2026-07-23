"""Touch / mouse gesture recognition for the radar display.

During development (no touch panel), mouse events substitute:
  - Click = Tap
  - Click + drag = Swipe
  - Scroll wheel = Zoom (pinch substitute)
"""

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import pygame

_SWIPE_THRESHOLD_PX = 40
_TAP_MAX_DURATION_S = 0.4
_TAP_MAX_MOVE_PX = 15


class GestureType(Enum):
    TAP = auto()
    SWIPE_UP = auto()
    SWIPE_DOWN = auto()
    SWIPE_LEFT = auto()
    SWIPE_RIGHT = auto()
    ZOOM_IN = auto()
    ZOOM_OUT = auto()


@dataclass
class Gesture:
    type: GestureType
    x: int
    y: int


class GestureRecogniser:
    def __init__(self) -> None:
        self._down_pos: Optional[tuple[int, int]] = None
        self._down_time: float = 0.0

    def process_event(self, event: pygame.event.Event) -> Optional[Gesture]:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._down_pos = event.pos
            self._down_time = time.monotonic()
            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._down_pos is None:
                return None
            dx = event.pos[0] - self._down_pos[0]
            dy = event.pos[1] - self._down_pos[1]
            dt = time.monotonic() - self._down_time
            start = self._down_pos
            self._down_pos = None

            dist = (dx * dx + dy * dy) ** 0.5
            if dist < _TAP_MAX_MOVE_PX and dt < _TAP_MAX_DURATION_S:
                return Gesture(GestureType.TAP, start[0], start[1])
            if dist >= _SWIPE_THRESHOLD_PX:
                if abs(dx) > abs(dy):
                    gt = GestureType.SWIPE_RIGHT if dx > 0 else GestureType.SWIPE_LEFT
                else:
                    gt = GestureType.SWIPE_DOWN if dy > 0 else GestureType.SWIPE_UP
                return Gesture(gt, start[0], start[1])
            return None

        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if event.y > 0:
                return Gesture(GestureType.ZOOM_IN, mx, my)
            if event.y < 0:
                return Gesture(GestureType.ZOOM_OUT, mx, my)

        return None

"""Unit tests for gesture recognition."""

import pygame
import pytest

from flugradar.display.gestures import GestureRecogniser, GestureType


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def gr():
    return GestureRecogniser()


def _mouse_down(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def _mouse_up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)


def _scroll(y):
    return pygame.event.Event(pygame.MOUSEWHEEL, y=y)


class TestTap:
    def test_simple_tap(self, gr):
        assert gr.process_event(_mouse_down((100, 100))) is None
        g = gr.process_event(_mouse_up((102, 101)))
        assert g is not None
        assert g.type == GestureType.TAP
        assert g.x == 100 and g.y == 100


class TestSwipe:
    def test_swipe_right(self, gr):
        gr.process_event(_mouse_down((100, 100)))
        g = gr.process_event(_mouse_up((200, 105)))
        assert g is not None
        assert g.type == GestureType.SWIPE_RIGHT

    def test_swipe_left(self, gr):
        gr.process_event(_mouse_down((200, 100)))
        g = gr.process_event(_mouse_up((100, 105)))
        assert g.type == GestureType.SWIPE_LEFT

    def test_swipe_up(self, gr):
        gr.process_event(_mouse_down((100, 200)))
        g = gr.process_event(_mouse_up((105, 100)))
        assert g.type == GestureType.SWIPE_UP

    def test_swipe_down(self, gr):
        gr.process_event(_mouse_down((100, 100)))
        g = gr.process_event(_mouse_up((105, 200)))
        assert g.type == GestureType.SWIPE_DOWN


class TestZoom:
    def test_zoom_in(self, gr):
        g = gr.process_event(_scroll(1))
        assert g is not None
        assert g.type == GestureType.ZOOM_IN

    def test_zoom_out(self, gr):
        g = gr.process_event(_scroll(-1))
        assert g.type == GestureType.ZOOM_OUT

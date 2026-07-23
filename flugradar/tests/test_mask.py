"""Unit tests for the circular viewport mask."""

import pygame
import pytest

from flugradar.display.mask import CircularViewport, create_circle_mask


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


class TestCircleMask:
    def test_mask_size(self):
        mask = create_circle_mask(720)
        assert mask.get_size() == (720, 720)

    def test_centre_transparent(self):
        mask = create_circle_mask(100)
        r, g, b, a = mask.get_at((50, 50))
        assert a == 0

    def test_corner_opaque(self):
        mask = create_circle_mask(100)
        r, g, b, a = mask.get_at((0, 0))
        assert a == 255


class TestCircularViewport:
    def test_apply_no_crash(self):
        vp = CircularViewport(200)
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        surf.fill((0, 255, 0, 255))
        vp.apply(surf)
        _, _, _, a_corner = surf.get_at((0, 0))
        assert a_corner > 0  # corner covered by mask

    def test_rotation(self):
        vp = CircularViewport(200, rotation_deg=90.0)
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        surf.fill((255, 0, 0, 255))
        vp.apply(surf)

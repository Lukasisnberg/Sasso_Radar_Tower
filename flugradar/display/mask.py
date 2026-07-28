"""Circular mask for the round display panel.

Renders all content inside a circle and blacks out the corners,
matching the physical shape of the Waveshare 4" round DSI LCD.
"""

from typing import Optional

import pygame

from flugradar.display.theme import CLASSIC_AMBER, Theme


def create_circle_mask(size: int) -> pygame.Surface:
    """Create an SRCALPHA surface that blacks out everything outside a circle."""
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 255))
    pygame.draw.circle(mask, (0, 0, 0, 0), (size // 2, size // 2), size // 2)
    return mask


def create_bezel_ring(
    size: int, width: int = 3, colour: tuple[int, int, int] = CLASSIC_AMBER.radar_ring
) -> pygame.Surface:
    """Thin ring drawn at the edge of the circular viewport for a bezel effect."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    radius = size // 2 - 1
    pygame.draw.circle(surf, (*colour, 200), (size // 2, size // 2), radius, width)
    return surf


class CircularViewport:
    """Manages the circular mask, bezel, and optional display rotation."""

    def __init__(self, size: int, rotation_deg: float = 0.0, theme: Optional[Theme] = None) -> None:
        self.size = size
        self.rotation_deg = rotation_deg
        self._mask = create_circle_mask(size)
        self._bezel = create_bezel_ring(size, colour=theme.radar_ring if theme else CLASSIC_AMBER.radar_ring)

    def update_theme(self, theme: Theme) -> None:
        """Rebuild the bezel ring to match a newly applied theme (live-reload)."""
        self._bezel = create_bezel_ring(self.size, colour=theme.radar_ring)

    def apply(self, surface: pygame.Surface, show_bezel: bool = True) -> None:
        if self.rotation_deg != 0.0:
            rotated = pygame.transform.rotate(surface, self.rotation_deg)
            rx = (rotated.get_width() - self.size) // 2
            ry = (rotated.get_height() - self.size) // 2
            surface.blit(rotated, (0, 0), area=pygame.Rect(rx, ry, self.size, self.size))

        surface.blit(self._mask, (0, 0))
        if show_bezel:
            surface.blit(self._bezel, (0, 0))

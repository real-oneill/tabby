"""Reusable chunky 8-bit UI widgets. All coordinates are in internal pixels."""

from __future__ import annotations

from typing import Callable, Optional, Sequence

import pygame

from .. import theme


def draw_panel(surface, rect, fill=theme.PANEL, border=theme.PANEL_BORDER, width=2):
    """Draw a filled rectangle with a chunky border."""
    rect = pygame.Rect(rect)
    surface.fill(fill, rect)
    if width > 0:
        pygame.draw.rect(surface, border, rect, width)


def draw_text(surface, text, size, color, center=None, topleft=None, midleft=None, midright=None):
    """Render pixel text and blit it, positioned by one of the anchor kwargs."""
    img = theme.font(size).render(text, False, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    elif topleft is not None:
        rect.topleft = topleft
    elif midleft is not None:
        rect.midleft = midleft
    elif midright is not None:
        rect.midright = midright
    surface.blit(img, rect)
    return rect


class Button:
    """A chunky touch-friendly button with a pressed state."""

    def __init__(
        self,
        rect: Sequence[int],
        text: str,
        on_click: Callable[[], None],
        color=theme.ACCENT,
        text_color=theme.BLACK,
        font_size: int = 12,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.text = text
        self.on_click = on_click
        self.color = color
        self.text_color = text_color
        self.font_size = font_size
        self._pressed = False

    def handle_event(self, event: pygame.event.Event, pos) -> bool:
        """Process an event using an internal-space mouse position.

        Returns True if this button consumed a click.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(pos):
                self._pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self._pressed
            self._pressed = False
            if was_pressed and self.rect.collidepoint(pos):
                self.on_click()
                return True
        return False

    def draw(self, surface) -> None:
        r = self.rect
        # Drop shadow / 3D edge.
        shadow = r.move(0, 2)
        pygame.draw.rect(surface, theme.BLACK, shadow)
        face = r.move(0, 2) if self._pressed else r
        surface.fill(self.color, face)
        pygame.draw.rect(surface, theme.WHITE, face, 1)
        draw_text(surface, self.text, self.font_size, self.text_color, center=face.center)


class Needle:
    """Horizontal tuner gauge: a marker that slides left/right of center.

    value in [-1, 1] maps across the gauge width; 0 is dead center / in tune.
    """

    def __init__(self, rect: Sequence[int]) -> None:
        self.rect = pygame.Rect(rect)

    def draw(self, surface, value: float, in_tune: bool) -> None:
        r = self.rect
        draw_panel(surface, r, fill=theme.DARK, border=theme.SHADOW, width=2)
        # Center reference line.
        cx = r.centerx
        center_color = theme.GOOD if in_tune else theme.SHADOW
        pygame.draw.rect(surface, center_color, (cx - 1, r.top + 2, 2, r.height - 4))
        # Tick marks at quarter positions.
        for frac in (-0.5, 0.5):
            tx = int(cx + frac * (r.width / 2 - 6))
            pygame.draw.rect(surface, theme.SHADOW, (tx - 1, r.centery - 3, 2, 6))
        # The moving marker.
        value = max(-1.0, min(1.0, value))
        mx = int(cx + value * (r.width / 2 - 6))
        color = theme.GOOD if in_tune else theme.WARN
        pygame.draw.rect(surface, color, (mx - 3, r.top + 1, 6, r.height - 2))


class BeatDots:
    """A row of dots that light up on the current beat; beat 1 can be accented."""

    def __init__(self, center, count: int, spacing: int = 28, radius: int = 7) -> None:
        self.center = center
        self.count = count
        self.spacing = spacing
        self.radius = radius

    def draw(self, surface, active_index: int, accent_beat_one: bool) -> None:
        total_w = (self.count - 1) * self.spacing
        x0 = self.center[0] - total_w // 2
        y = self.center[1]
        for i in range(self.count):
            x = x0 + i * self.spacing
            is_active = i == active_index
            is_one = i == 0
            if is_active:
                color = theme.RED if (is_one and accent_beat_one) else theme.ACCENT
            else:
                color = theme.SHADOW
            pygame.draw.rect(
                surface, color, (x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)
            )
            outline = theme.WHITE if is_one else theme.PANEL_BORDER
            pygame.draw.rect(
                surface,
                outline,
                (x - self.radius, y - self.radius, self.radius * 2, self.radius * 2),
                1,
            )

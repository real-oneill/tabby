"""Render a windowed slice of a text tab in the 8-bit monospace style."""

from __future__ import annotations

import pygame

from .. import theme
from ..ui.widgets import draw_panel

_BODY_SIZE = 8       # PressStart2P is fixed-width; size 8 reads cleanly after x2 upscale
_LINE_GAP = 2
_LEFT_PAD = 6


def line_height() -> int:
    return theme.font(_BODY_SIZE).get_height() + _LINE_GAP


def char_width() -> int:
    return theme.font(_BODY_SIZE).size("0")[0]


def draw(surface, tab, scroller, area: pygame.Rect) -> None:
    """Draw the visible lines of ``tab`` within ``area`` given the scroll state."""
    draw_panel(surface, area, fill=theme.DARK, border=theme.PANEL_BORDER, width=1)
    prev_clip = surface.get_clip()
    surface.set_clip(area)

    font = theme.font(_BODY_SIZE)
    lh = line_height()
    base_x = area.x + _LEFT_PAD - int(scroller.h_offset)

    # First visible line index and its sub-line pixel offset.
    first = int(scroller.offset)
    frac = scroller.offset - first
    y = area.y + 2 - int(frac * lh)

    i = first
    while y < area.bottom and i < len(tab.lines):
        line = tab.lines[i]
        if line:
            # Color tab/number lines a touch brighter than lyric/chord text.
            color = theme.TEXT if _looks_like_tab(line) else theme.TEXT_DIM
            img = font.render(line, False, color)
            surface.blit(img, (base_x, y))
        y += lh
        i += 1

    surface.set_clip(prev_clip)

    # Lightweight position indicator down the right edge.
    if scroller.max_offset > 0:
        track_h = area.height - 8
        knob_y = area.y + 4 + int(track_h * (scroller.offset / scroller.max_offset))
        pygame.draw.rect(surface, theme.SHADOW, (area.right - 4, area.y + 4, 2, track_h))
        pygame.draw.rect(surface, theme.ACCENT, (area.right - 5, knob_y, 4, 6))


def _looks_like_tab(line: str) -> bool:
    """Heuristic: tab staff lines are dense with '-' and digits/string letters."""
    dashes = line.count("-")
    return dashes >= 4 or (dashes >= 2 and "|" in line)

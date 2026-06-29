"""Horizontal scale-neck diagram.

Reuses ``render_synced``'s row idiom: **row 0 (top) = string 1 (high E)**, so the
diagram lines up with the play-along view. Strings run horizontally, frets are
columns; root tones are highlighted, other scale tones are dimmer.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..ui.widgets import draw_text
from .library import ScalePosition

_GUT = 20             # left gutter (open-string column / nut)
_GRID = (48, 40, 60)  # faint fret wire, matching render_synced


def draw_neck(surface, position: ScalePosition, area: pygame.Rect) -> None:
    n = 6
    top = area.y + 22
    bottom = area.bottom - 14
    span = bottom - top
    rows = [int(top + span * i / (n - 1)) for i in range(n)]   # row i -> string i+1

    nut_x = area.x + _GUT
    lo1 = max(position.fret_lo, 1)
    count = max(1, position.fret_hi - lo1 + 1)
    cell_w = (area.right - 6 - nut_x) / count
    has_open = position.fret_lo == 0

    def cx(fret: int) -> int:
        if fret == 0:
            return int(area.x + _GUT // 2)
        return int(nut_x + (fret - lo1 + 0.5) * cell_w)

    # String lines.
    for y in rows:
        pygame.draw.line(surface, theme.SHADOW, (area.x + 4, y), (area.right - 4, y), 1)

    # Fret wires + nut.
    for k in range(count + 1):
        x = int(nut_x + k * cell_w)
        pygame.draw.line(surface, _GRID, (x, top), (x, bottom), 1)
    pygame.draw.line(surface, theme.TEXT if has_open else theme.SHADOW,
                     (nut_x, top), (nut_x, bottom), 2 if has_open else 1)

    # Fret-number labels.
    for f in range(lo1, position.fret_hi + 1):
        draw_text(surface, str(f), 8, theme.TEXT_DIM, center=(cx(f), area.bottom - 6))

    # Scale-tone dots.
    for hit in position.hits:
        is_root = (hit.string, hit.fret) in position.roots
        color = theme.ACCENT if is_root else theme.ACCENT_ALT
        c = (cx(hit.fret), rows[hit.string - 1])
        pygame.draw.circle(surface, color, c, 4)
        pygame.draw.circle(surface, theme.WHITE, c, 4, 1)

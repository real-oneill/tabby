"""Vertical chord-box diagram (clean line + dot).

Standard chord-chart orientation: **string 6 (low E) on the LEFT, string 1 (high E)
on the RIGHT** — the mirror of ``render_synced``'s top-to-bottom rows. Strings run
vertically, frets horizontally; dots carry finger numbers, X/O sit above the nut.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..ui.widgets import draw_text
from .library import MUTED, ChordPosition

_ROWS = 5            # fret rows shown
_MARKER_H = 12       # band above the nut for X / O markers
_LBL_W = 24          # left column for the base-fret number
_COL_CAP = 26        # max px between strings (keeps the box from ballooning)
_ROW_CAP = 24        # max px between fret wires


def draw_chord(surface, position: ChordPosition, area: pygame.Rect) -> None:
    col_gap = int(min((area.width - _LBL_W - 8) / 5, _COL_CAP))
    row_gap = int(min((area.height - _MARKER_H - 8) / _ROWS, _ROW_CAP))
    gw, gh = col_gap * 5, row_gap * _ROWS
    gx = area.left + _LBL_W + (area.width - _LBL_W - gw) // 2
    gy = area.top + _MARKER_H + max(0, (area.height - _MARKER_H - gh) // 2)

    def x_of(string: int) -> int:
        return int(gx + (6 - string) * col_gap)   # string 6 left, string 1 right

    def row_y(row: int) -> int:                    # row 1..5 -> center of that fret cell
        return int(gy + (row - 0.5) * row_gap)

    open_top = position.base_fret == 1
    dot_r = int(col_gap * 0.40)

    # Horizontal fret wires.
    for j in range(_ROWS + 1):
        y = gy + j * row_gap
        wire = (open_top and j == 0)
        pygame.draw.line(surface, theme.TEXT if wire else theme.SHADOW,
                         (gx, y), (gx + gw, y), 2 if wire else 1)
    # Vertical string lines.
    for s in range(1, 7):
        x = x_of(s)
        pygame.draw.line(surface, theme.SHADOW, (x, gy), (x, gy + gh), 1)

    # Base-fret number for shapes that don't start at the nut (left of the dots).
    if not open_top:
        draw_text(surface, str(position.base_fret), 8, theme.TEXT_DIM,
                  midright=(x_of(6) - dot_r - 3, row_y(1)))

    # Barre capsule (behind the dots), drawn at the barre's own fret row.
    if position.barre is not None:
        _, s_from, s_to, b_fret = position.barre
        b_row = b_fret - position.base_fret + 1
        if 1 <= b_row <= _ROWS:
            xa, xb = sorted((x_of(s_from), x_of(s_to)))
            y = row_y(b_row)
            surface.fill(theme.ACCENT, (xa, y - dot_r, xb - xa, 2 * dot_r))
            pygame.draw.circle(surface, theme.ACCENT, (xa, y), dot_r)
            pygame.draw.circle(surface, theme.ACCENT, (xb, y), dot_r)

    # Per-string markers + dots.
    for hit in position.hits:
        x = x_of(hit.string)
        if hit.fret == MUTED:
            draw_text(surface, "X", 8, theme.TEXT_DIM, center=(x, area.top + _MARKER_H // 2))
            continue
        if hit.fret == 0:
            draw_text(surface, "O", 8, theme.GOOD, center=(x, area.top + _MARKER_H // 2))
            continue
        row = hit.fret - position.base_fret + 1
        if not (1 <= row <= _ROWS):
            continue
        c = (x, row_y(row))
        pygame.draw.circle(surface, theme.ACCENT, c, dot_r)
        pygame.draw.circle(surface, theme.WHITE, c, dot_r, 1)
        if hit.finger:
            draw_text(surface, str(hit.finger), 8, theme.BLACK, center=c)

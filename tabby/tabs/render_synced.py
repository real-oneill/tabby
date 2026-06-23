"""Render the timed model as a horizontal tab staff scrolling under a playhead."""

from __future__ import annotations

import pygame

from .. import theme
from ..ui.widgets import draw_panel, draw_text

PX_PER_BEAT = 26          # horizontal pixels per quarter-note beat
_CURSOR_DX = 70           # playhead x offset from the staff's left edge
_GUTTER = 22              # left gutter for string tuning labels

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_GRID = (48, 40, 60)      # faint measure divider


def midi_name(midi: int) -> str:
    return _NOTE_NAMES[midi % 12]


def beats_per_pixel() -> float:
    return 1.0 / PX_PER_BEAT


def draw(surface, player, area: pygame.Rect) -> None:
    draw_panel(surface, area, fill=theme.DARK, border=theme.PANEL_BORDER, width=1)
    prev_clip = surface.get_clip()
    surface.set_clip(area)

    track = player.track
    n = max(1, track.string_count)
    top = area.y + 12
    bottom = area.bottom - 10
    span = bottom - top
    rows = [top + (span * i / (n - 1) if n > 1 else span / 2) for i in range(n)]
    cursor_x = area.x + _GUTTER + _CURSOR_DX

    # Measure grid (faint vertical line every 4 beats) for orientation.
    first_measure = int(player.pos // 4) * 4
    m = first_measure
    while True:
        x = cursor_x + (m - player.pos) * PX_PER_BEAT
        if x > area.right:
            break
        if x >= area.x + _GUTTER:
            pygame.draw.line(surface, _GRID, (x, top), (x, bottom), 1)
        m += 4

    # String lines + tuning labels.
    for i, y in enumerate(rows):
        yy = int(y)
        pygame.draw.line(surface, theme.SHADOW, (area.x + _GUTTER, yy), (area.right - 4, yy), 1)
        draw_text(surface, midi_name(track.tuning[i]), 8, theme.TEXT_DIM, center=(area.x + 11, yy))

    # Loop region shading + markers.
    if player.loop_a is not None:
        ax = cursor_x + (player.loop_a - player.pos) * PX_PER_BEAT
        bx = cursor_x + (player.loop_b - player.pos) * PX_PER_BEAT if player.loop_b is not None else ax
        if player.loop_b is not None:
            shade = pygame.Surface((max(1, int(bx - ax)), int(bottom - top)))
            shade.set_alpha(40)
            shade.fill(theme.CYAN)
            surface.blit(shade, (int(ax), int(top)))
        pygame.draw.line(surface, theme.CYAN, (int(ax), top), (int(ax), bottom), 1)
        if player.loop_b is not None:
            pygame.draw.line(surface, theme.MAGENTA, (int(bx), top), (int(bx), bottom), 1)

    # Notes.
    active = player.current_beat_index()
    for idx, beat in enumerate(track.beats):
        x = cursor_x + (beat.start - player.pos) * PX_PER_BEAT
        if x < area.x + _GUTTER - 8 or x > area.right + 8:
            continue
        color = theme.GOOD if idx == active else theme.TEXT
        for note in beat.notes:
            row = note.string - 1
            if 0 <= row < n:
                draw_text(surface, str(note.fret), 8, color, center=(int(x), int(rows[row])))

    # Playhead.
    pygame.draw.rect(surface, theme.ACCENT, (cursor_x - 1, top - 4, 2, span + 8))

    surface.set_clip(prev_clip)

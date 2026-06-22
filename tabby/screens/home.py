"""Home menu: a grid of tool tiles routing to each screen."""

from __future__ import annotations

import pygame

from .. import theme
from ..app import Screen, TOPBAR_H
from ..ui.widgets import Button, draw_text


class HomeScreen(Screen):
    title = "TABBY"
    show_back = False

    # (label, screen name, color key)
    TILES = [
        ("TUNER", "tuner", "tuner"),
        ("METRO", "metronome", "metronome"),
        ("TABS", "tabs", "tabs"),
        ("ASSIST", "assistant", "assistant"),
        ("CONFIG", "settings", "settings"),
    ]

    def __init__(self, app) -> None:
        super().__init__(app)
        self.buttons: list[Button] = []
        # 3 columns; tiles sized to the content area below the top bar.
        cols = 3
        margin = 12
        gap = 10
        area_top = TOPBAR_H + margin
        usable_w = theme.INTERNAL_W - 2 * margin
        tile_w = (usable_w - (cols - 1) * gap) // cols
        tile_h = 64
        for i, (label, name, color_key) in enumerate(self.TILES):
            row, col = divmod(i, cols)
            x = margin + col * (tile_w + gap)
            y = area_top + row * (tile_h + gap)
            color = theme.TOOL_COLORS[color_key]
            self.buttons.append(
                Button((x, y, tile_w, tile_h), label, self._go(name),
                       color=color, text_color=theme.BLACK, font_size=12)
            )

    def _go(self, name: str):
        return lambda: self.app.navigate(name)

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        for btn in self.buttons:
            btn.handle_event(event, pos)

    def draw(self, surface) -> None:
        for btn in self.buttons:
            btn.draw(surface)
        draw_text(
            surface, "PRACTICE ASSISTANT", 8, theme.TEXT_DIM,
            center=(theme.INTERNAL_W // 2, theme.INTERNAL_H - 12),
        )

"""Home menu: a grid of tool tiles routing to each screen."""

from __future__ import annotations

import subprocess
import sys

import pygame

from .. import theme
from ..app import Screen, TOPBAR_H
from ..ui.widgets import Button, draw_panel, draw_text

# Power-off only makes sense on the Pi (Linux); hidden on the dev Mac.
_CAN_POWER_OFF = sys.platform.startswith("linux")
_POWEROFF_CMD = ["sudo", "-n", "/usr/sbin/poweroff"]


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
        self.confirming = False
        self.shutting_down = False
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

        # POWER tile fills the empty sixth grid slot (row 1, col 2).
        self.power_btn = None
        if _CAN_POWER_OFF:
            row, col = divmod(len(self.TILES), cols)
            x = margin + col * (tile_w + gap)
            y = area_top + row * (tile_h + gap)
            self.power_btn = Button((x, y, tile_w, tile_h), "POWER", self._ask_power_off,
                                    color=theme.RED, text_color=theme.WHITE, font_size=12)

        # Confirmation modal buttons (only used while self.confirming).
        modal = pygame.Rect(0, 0, 220, 96)
        modal.center = (theme.INTERNAL_W // 2, theme.INTERNAL_H // 2)
        self.modal_rect = modal
        by = modal.bottom - 34
        self.confirm_buttons = [
            Button((modal.left + 22, by, 78, 24), "NO", self._cancel_power_off,
                   color=theme.SHADOW, text_color=theme.WHITE, font_size=10),
            Button((modal.right - 100, by, 78, 24), "YES", self._do_power_off,
                   color=theme.RED, text_color=theme.WHITE, font_size=10),
        ]

    def _go(self, name: str):
        return lambda: self.app.navigate(name)

    def _ask_power_off(self) -> None:
        self.confirming = True

    def _cancel_power_off(self) -> None:
        self.confirming = False

    def _do_power_off(self) -> None:
        self.shutting_down = True
        self.confirming = False
        try:
            subprocess.Popen(_POWEROFF_CMD)
        except Exception:
            self.shutting_down = False

    def handle_event(self, event, pos) -> None:
        if pos is None or self.shutting_down:
            return
        if self.confirming:
            for btn in self.confirm_buttons:
                btn.handle_event(event, pos)
            return
        for btn in self.buttons:
            btn.handle_event(event, pos)
        if self.power_btn is not None:
            self.power_btn.handle_event(event, pos)

    def draw(self, surface) -> None:
        for btn in self.buttons:
            btn.draw(surface)
        if self.power_btn is not None:
            self.power_btn.draw(surface)
        draw_text(
            surface, "PRACTICE ASSISTANT", 8, theme.TEXT_DIM,
            center=(theme.INTERNAL_W // 2, theme.INTERNAL_H - 12),
        )

        if self.shutting_down:
            self._draw_modal(surface, "SHUTTING DOWN...", buttons=False)
        elif self.confirming:
            self._draw_modal(surface, "POWER OFF?", buttons=True)

    def _draw_modal(self, surface, message: str, buttons: bool) -> None:
        draw_panel(surface, self.modal_rect, fill=theme.PANEL, border=theme.RED, width=2)
        cx = self.modal_rect.centerx
        draw_text(surface, message, 10, theme.TEXT,
                  center=(cx, self.modal_rect.top + 28))
        if buttons:
            for btn in self.confirm_buttons:
                btn.draw(surface)

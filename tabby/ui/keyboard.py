"""A compact on-screen touch keyboard for the 400x240 canvas."""

from __future__ import annotations

from typing import Callable

from .. import theme
from .widgets import Button, draw_panel, draw_text

_ROWS = ["1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]


class Keyboard:
    """Text entry via on-screen keys. Calls ``on_submit(text)`` on GO."""

    def __init__(self, on_submit: Callable[[str], None], on_cancel: Callable[[], None] | None = None,
                 text: str = "", prompt: str = "SEARCH") -> None:
        self.text = text
        self.prompt = prompt
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        self.buttons: list[Button] = []
        self._build()

    def _build(self) -> None:
        kw, kh, gap = 36, 26, 2
        top = 50
        for r, row in enumerate(_ROWS):
            y = top + r * (kh + gap)
            row_w = len(row) * (kw + gap) - gap
            x0 = (theme.INTERNAL_W - row_w) // 2
            for i, ch in enumerate(row):
                x = x0 + i * (kw + gap)
                self.buttons.append(Button((x, y, kw, kh), ch, self._typer(ch),
                                          color=theme.PANEL, text_color=theme.TEXT, font_size=10))

        # Cancel chip in the query-field row (only if a handler was provided).
        if self.on_cancel is not None:
            self.buttons.append(Button((theme.INTERNAL_W - 32, 26, 20, 18), "X", self.on_cancel,
                                      color=theme.SHADOW, text_color=theme.WHITE, font_size=8))

        # Bottom row: DEL, SPACE (wide), CLEAR, GO.
        y = top + len(_ROWS) * (kh + gap) + 4
        self.buttons.append(Button((10, y, 60, kh), "DEL", self._backspace, color=theme.SHADOW, text_color=theme.WHITE, font_size=8))
        self.buttons.append(Button((74, y, 150, kh), "SPACE", lambda: self._type(" "), color=theme.PANEL, text_color=theme.TEXT, font_size=8))
        self.buttons.append(Button((228, y, 60, kh), "CLR", self._clear, color=theme.SHADOW, text_color=theme.WHITE, font_size=8))
        self.buttons.append(Button((292, y, 98, kh), "GO", self._submit, color=theme.GOOD, text_color=theme.BLACK, font_size=12))

    def _typer(self, ch: str):
        return lambda: self._type(ch)

    def _type(self, ch: str) -> None:
        if len(self.text) < 40:
            self.text += ch

    def _backspace(self) -> None:
        self.text = self.text[:-1]

    def _clear(self) -> None:
        self.text = ""

    def _submit(self) -> None:
        if self.text.strip():
            self.on_submit(self.text.strip())

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        for btn in self.buttons:
            if btn.handle_event(event, pos):
                return

    def draw(self, surface) -> None:
        # Query field.
        field = (10, 26, theme.INTERNAL_W - 20, 18)
        draw_panel(surface, field, fill=theme.DARK, border=theme.PANEL_BORDER, width=1)
        shown = self.text if self.text else self.prompt + "..."
        color = theme.TEXT if self.text else theme.TEXT_DIM
        draw_text(surface, shown[-44:] + ("_" if self.text else ""), 8, color, midleft=(16, 35))
        for btn in self.buttons:
            btn.draw(surface)

"""Settings: audio input/output device pickers and the tuning reference."""

from __future__ import annotations

from .. import theme
from ..app import Screen
from ..ui.widgets import Button, draw_text


def _truncate(name: str, n: int = 34) -> str:
    return name if len(name) <= n else name[: n - 1] + "~"


class SettingsScreen(Screen):
    title = "CONFIG"

    def __init__(self, app) -> None:
        super().__init__(app)
        audio = app.audio
        self.input_opts = [(None, "DEFAULT")] + audio.list_devices("input")
        self.output_opts = [(None, "DEFAULT")] + audio.list_devices("output")
        self.in_idx = self._index_of(self.input_opts, app.config.get("input_device"))
        self.out_idx = self._index_of(self.output_opts, app.config.get("output_device"))

        self.buttons = [
            Button((20, 50, 26, 24), "<", lambda: self._cycle("in", -1), color=theme.SHADOW, text_color=theme.WHITE),
            Button((354, 50, 26, 24), ">", lambda: self._cycle("in", 1), color=theme.SHADOW, text_color=theme.WHITE),
            Button((20, 102, 26, 24), "<", lambda: self._cycle("out", -1), color=theme.SHADOW, text_color=theme.WHITE),
            Button((354, 102, 26, 24), ">", lambda: self._cycle("out", 1), color=theme.SHADOW, text_color=theme.WHITE),
            Button((120, 158, 26, 24), "-", lambda: self._tune(-1), color=theme.SHADOW, text_color=theme.WHITE),
            Button((254, 158, 26, 24), "+", lambda: self._tune(1), color=theme.SHADOW, text_color=theme.WHITE),
        ]

    @staticmethod
    def _index_of(opts, value) -> int:
        for i, (val, _name) in enumerate(opts):
            if val == value:
                return i
        return 0

    def _cycle(self, which: str, delta: int) -> None:
        if which == "in":
            self.in_idx = (self.in_idx + delta) % len(self.input_opts)
            self.app.config.set("input_device", self.input_opts[self.in_idx][0])
        else:
            self.out_idx = (self.out_idx + delta) % len(self.output_opts)
            self.app.config.set("output_device", self.output_opts[self.out_idx][0])

    def _tune(self, delta: int) -> None:
        a4 = max(430.0, min(450.0, self.app.config.get("a4_hz") + delta))
        self.app.config.set("a4_hz", a4)

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        for btn in self.buttons:
            btn.handle_event(event, pos)

    def draw(self, surface) -> None:
        cx = theme.INTERNAL_W // 2
        for btn in self.buttons:
            btn.draw(surface)

        draw_text(surface, "MIC INPUT", 8, theme.ACCENT_ALT, center=(cx, 40))
        draw_text(surface, _truncate(self.input_opts[self.in_idx][1]), 8, theme.TEXT, center=(cx, 62))

        draw_text(surface, "AUDIO OUTPUT", 8, theme.ORANGE, center=(cx, 92))
        draw_text(surface, _truncate(self.output_opts[self.out_idx][1]), 8, theme.TEXT, center=(cx, 114))

        draw_text(surface, "TUNING REF  (A4)", 8, theme.TEXT_DIM, center=(cx, 148))
        draw_text(surface, f"{self.app.config.get('a4_hz'):.0f} HZ", 12, theme.TEXT, center=(cx, 170))

        draw_text(surface, "CHANGES APPLY NEXT TIME A TOOL OPENS", 8, theme.TEXT_DIM,
                  center=(cx, 214))

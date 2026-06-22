"""Metronome screen: tempo / tap-tempo, time signature, accent, synced beat dots."""

from __future__ import annotations

import time

from .. import theme
from ..app import Screen
from ..audio.click import Metronome, make_click
from ..ui.widgets import BeatDots, Button, draw_text

_TEMPO_MIN = 30
_TEMPO_MAX = 300
_TAP_TIMEOUT = 2.0  # forget taps older than this


class MetronomeScreen(Screen):
    title = "METRONOME"

    def __init__(self, app) -> None:
        super().__init__(app)
        cfg = app.config
        self._click = make_click(accent=False)
        self._accent_click = make_click(accent=True)
        self.metro = Metronome(self._play)
        self.metro.tempo = int(cfg.get("tempo"))
        self.metro.beats_per_measure = int(cfg.get("beats_per_measure"))
        self.metro.accent = bool(cfg.get("accent_beat_one"))
        self.tap_times: list[float] = []
        self.no_audio = False

        self.dots = BeatDots((theme.INTERNAL_W // 2, 134), self.metro.beats_per_measure)

        self.buttons = [
            Button((36, 84, 34, 26), "-5", lambda: self._adjust(-5), color=theme.SHADOW, text_color=theme.WHITE, font_size=10),
            Button((74, 84, 34, 26), "-1", lambda: self._adjust(-1), color=theme.SHADOW, text_color=theme.WHITE, font_size=10),
            Button((148, 80, 104, 30), "TAP", self._tap, color=theme.ACCENT_ALT, text_color=theme.BLACK, font_size=12),
            Button((292, 84, 34, 26), "+1", lambda: self._adjust(1), color=theme.SHADOW, text_color=theme.WHITE, font_size=10),
            Button((330, 84, 34, 26), "+5", lambda: self._adjust(5), color=theme.SHADOW, text_color=theme.WHITE, font_size=10),
            Button((118, 152, 24, 22), "-", lambda: self._adjust_beats(-1), color=theme.SHADOW, text_color=theme.WHITE, font_size=12),
            Button((258, 152, 24, 22), "+", lambda: self._adjust_beats(1), color=theme.SHADOW, text_color=theme.WHITE, font_size=12),
            Button((12, 152, 64, 22), "ACCENT", self._toggle_accent, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
            Button((110, 186, 180, 34), "START", self._toggle_run, color=theme.GOOD, text_color=theme.BLACK, font_size=14),
        ]
        self._run_btn = self.buttons[-1]
        self._accent_btn = self.buttons[-2]

    # --- Lifecycle --------------------------------------------------------

    def on_enter(self) -> None:
        self.no_audio = not self.app.audio.start_output()

    def on_exit(self) -> None:
        self.metro.stop()
        self.app.audio.stop_output()
        self._save()

    def _play(self, accent: bool) -> None:
        self.app.audio.play_sample(self._accent_click if accent else self._click)

    # --- Actions ----------------------------------------------------------

    def _adjust(self, delta: int) -> None:
        self.metro.tempo = max(_TEMPO_MIN, min(_TEMPO_MAX, self.metro.tempo + delta))

    def _adjust_beats(self, delta: int) -> None:
        self.metro.beats_per_measure = max(1, min(12, self.metro.beats_per_measure + delta))
        self.dots.count = self.metro.beats_per_measure

    def _toggle_accent(self) -> None:
        self.metro.accent = not self.metro.accent

    def _toggle_run(self) -> None:
        self.metro.toggle()

    def _tap(self) -> None:
        now = time.perf_counter()
        if self.tap_times and now - self.tap_times[-1] > _TAP_TIMEOUT:
            self.tap_times.clear()
        self.tap_times.append(now)
        if len(self.tap_times) >= 2:
            intervals = [b - a for a, b in zip(self.tap_times, self.tap_times[1:])]
            avg = sum(intervals[-4:]) / len(intervals[-4:])
            if avg > 0:
                self.metro.tempo = max(_TEMPO_MIN, min(_TEMPO_MAX, round(60.0 / avg)))

    def _save(self) -> None:
        cfg = self.app.config
        cfg.set("tempo", self.metro.tempo)
        cfg.set("beats_per_measure", self.metro.beats_per_measure)
        cfg.set("accent_beat_one", self.metro.accent)

    # --- Events / draw ----------------------------------------------------

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        for btn in self.buttons:
            btn.handle_event(event, pos)

    def update(self, dt: float) -> None:
        self._run_btn.text = "STOP" if self.metro.running else "START"
        self._run_btn.color = theme.BAD if self.metro.running else theme.GOOD
        self._accent_btn.color = theme.ORANGE if self.metro.accent else theme.PANEL

    def draw(self, surface) -> None:
        cx = theme.INTERNAL_W // 2
        if self.no_audio:
            draw_text(surface, "NO AUDIO OUT", 12, theme.BAD, center=(cx, 50))
            draw_text(surface, "CHECK OUTPUT IN CONFIG", 8, theme.TEXT_DIM, center=(cx, 70))

        draw_text(surface, str(self.metro.tempo), 32, theme.TEXT, center=(cx, 48))
        draw_text(surface, "BPM", 8, theme.TEXT_DIM, center=(cx, 70))

        for btn in self.buttons:
            btn.draw(surface)

        # Beat dots, synced to the scheduler thread.
        self.dots.draw(surface, self.metro.current_beat, self.metro.accent)

        # Time signature label between its -/+ buttons.
        draw_text(surface, f"{self.metro.beats_per_measure} BEATS", 10, theme.TEXT,
                  center=(cx, 163))

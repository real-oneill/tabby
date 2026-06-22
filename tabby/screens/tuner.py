"""Tuner screen: mic -> pitch detection -> 8-bit note display with a needle."""

from __future__ import annotations

from .. import theme
from ..app import Screen
from ..audio import pitch
from ..audio.engine import SAMPLE_RATE
from ..ui.widgets import Needle, draw_text

_WINDOW = 2048          # samples fed to the detector
_DETECT_INTERVAL = 0.04  # seconds between detections
_IN_TUNE_CENTS = 5.0
_HOLD_TIME = 0.4         # keep showing the last note this long after silence


class TunerScreen(Screen):
    title = "TUNER"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.reading = None
        self.smooth_cents = 0.0
        self.since_detect = 0.0
        self.since_sound = 99.0
        self.needle = Needle((60, 150, theme.INTERNAL_W - 120, 28))
        self.no_audio = False

    def on_enter(self) -> None:
        self.no_audio = not self.app.audio.start_input()

    def on_exit(self) -> None:
        self.app.audio.stop_input()

    def update(self, dt: float) -> None:
        self.since_detect += dt
        self.since_sound += dt
        if self.since_detect < _DETECT_INTERVAL:
            return
        self.since_detect = 0.0

        window = self.app.audio.read_window(_WINDOW)
        freq = pitch.detect_frequency(window, SAMPLE_RATE)
        if freq is not None:
            reading = pitch.frequency_to_note(freq, self.app.config.get("a4_hz"))
            self.reading = reading
            # Smooth cents for a steadier needle.
            self.smooth_cents += (reading.cents - self.smooth_cents) * 0.4
            self.since_sound = 0.0

    @property
    def _in_tune(self) -> bool:
        return self.reading is not None and abs(self.smooth_cents) < _IN_TUNE_CENTS

    def draw(self, surface) -> None:
        cx = theme.INTERNAL_W // 2

        if self.no_audio:
            draw_text(surface, "NO MIC", 16, theme.BAD, center=(cx, 90))
            draw_text(surface, "CHECK INPUT IN CONFIG", 8, theme.TEXT_DIM, center=(cx, 120))
            return

        listening = self.reading is None or self.since_sound > _HOLD_TIME

        if listening:
            draw_text(surface, "- -", 28, theme.TEXT_DIM, center=(cx, 80))
            draw_text(surface, "LISTENING...", 8, theme.TEXT_DIM, center=(cx, 116))
        else:
            r = self.reading
            color = theme.GOOD if self._in_tune else theme.TEXT
            draw_text(surface, r.name, 40, color, center=(cx - 14, 80))
            draw_text(surface, str(r.octave), 16, theme.TEXT_DIM, topleft=(cx + 26, 86))
            draw_text(surface, f"{r.freq:6.1f} HZ", 8, theme.TEXT_DIM, center=(cx, 118))

        # Needle gauge.
        value = self.smooth_cents / 50.0 if not listening else 0.0
        self.needle.draw(surface, value, self._in_tune and not listening)

        # Cents readout / status.
        if listening:
            status, scol = "", theme.TEXT_DIM
        elif self._in_tune:
            status, scol = "IN TUNE", theme.GOOD
        else:
            sign = "+" if self.smooth_cents > 0 else "-"
            status = f"{sign}{abs(self.smooth_cents):2.0f} CENTS"
            scol = theme.WARN
        if status:
            draw_text(surface, status, 10, scol, center=(cx, 200))

        # Flat/sharp hints at the gauge ends.
        draw_text(surface, "b", 10, theme.TEXT_DIM, center=(40, 164))
        draw_text(surface, "#", 10, theme.TEXT_DIM, center=(theme.INTERNAL_W - 40, 164))

"""Metronome click synthesis and a drift-corrected scheduler thread."""

from __future__ import annotations

import threading
import time
from typing import Callable

import numpy as np

from .engine import SAMPLE_RATE


def make_click(accent: bool, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """A short percussive click: a high-pitched sine burst with fast decay."""
    freq = 1600.0 if accent else 1000.0
    dur = 0.035
    n = int(sample_rate * dur)
    t = np.arange(n) / sample_rate
    env = np.exp(-t * 130.0)
    amp = 0.85 if accent else 0.55
    tone = np.sin(2 * np.pi * freq * t) * env * amp
    return tone.astype(np.float32)


class Metronome:
    """Schedules beats on a background thread and reports the current beat.

    `play_fn(accent: bool)` is invoked on each beat (it should be non-blocking).
    Tempo and time signature can be changed live; the next interval picks them up.
    """

    def __init__(self, play_fn: Callable[[bool], None]) -> None:
        self.play_fn = play_fn
        self.tempo = 120
        self.beats_per_measure = 4
        self.accent = True
        self.running = False
        self.current_beat = -1
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.current_beat = -1
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None
        self.current_beat = -1

    def toggle(self) -> None:
        self.stop() if self.running else self.start()

    def _run(self) -> None:
        beat = 0
        next_t = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            if now >= next_t:
                accent = self.accent and (beat % max(1, self.beats_per_measure) == 0)
                self.current_beat = beat % max(1, self.beats_per_measure)
                self.play_fn(accent)
                interval = 60.0 / self.tempo
                next_t += interval
                beat += 1
                # If we fell badly behind (e.g. after a stall), resync.
                if time.perf_counter() - next_t > interval:
                    next_t = time.perf_counter() + interval
            else:
                time.sleep(min(0.001, max(0.0, next_t - now)))

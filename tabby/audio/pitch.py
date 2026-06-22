"""Monophonic pitch detection via the YIN algorithm, plus note mapping.

Pure numpy, so there's no fragile native dependency to build on the Pi.
"""

from __future__ import annotations

import math
from typing import NamedTuple, Optional

import numpy as np

# Search range covers the guitar's useful range with margin: ~73 Hz to ~1.4 kHz.
_TAU_MIN = 32
_TAU_MAX = 600
_YIN_THRESHOLD = 0.12
_RMS_GATE = 0.004  # below this, treat as silence

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class NoteReading(NamedTuple):
    freq: float
    name: str       # e.g. "E"
    octave: int     # e.g. 2
    cents: float    # signed offset from the nearest semitone, -50..+50

    @property
    def label(self) -> str:
        return f"{self.name}{self.octave}"


def detect_frequency(samples: np.ndarray, sample_rate: int) -> Optional[float]:
    """Return the fundamental frequency in Hz, or None if no clear pitch."""
    x = samples.astype(np.float64)
    x = x - x.mean()  # remove DC
    if math.sqrt(float(np.mean(x * x))) < _RMS_GATE:
        return None

    w = len(x)
    tau_max = min(_TAU_MAX, w // 2)
    if tau_max <= _TAU_MIN:
        return None

    # Difference function d(tau).
    d = np.zeros(tau_max)
    for tau in range(1, tau_max):
        diff = x[: w - tau] - x[tau:w]
        d[tau] = np.dot(diff, diff)

    # Cumulative mean normalized difference d'(tau).
    cmnd = np.ones(tau_max)
    running = np.cumsum(d[1:])
    taus = np.arange(1, tau_max)
    # Avoid divide-by-zero; where running==0 leave cmnd at 1.
    nonzero = running > 0
    cmnd[1:][nonzero] = d[1:][nonzero] * taus[nonzero] / running[nonzero]

    # Find the first tau below threshold that is a local minimum.
    tau = _TAU_MIN
    best_tau = -1
    while tau < tau_max - 1:
        if cmnd[tau] < _YIN_THRESHOLD:
            while tau + 1 < tau_max and cmnd[tau + 1] < cmnd[tau]:
                tau += 1
            best_tau = tau
            break
        tau += 1

    if best_tau == -1:
        # No value crossed the threshold; fall back to the global minimum.
        best_tau = int(np.argmin(cmnd[_TAU_MIN:tau_max])) + _TAU_MIN
        if cmnd[best_tau] > 0.5:
            return None

    refined = _parabolic_interp(cmnd, best_tau)
    if refined <= 0:
        return None
    return sample_rate / refined


def _parabolic_interp(arr: np.ndarray, i: int) -> float:
    """Refine the index of a local minimum with parabolic interpolation."""
    if i <= 0 or i >= len(arr) - 1:
        return float(i)
    a, b, c = arr[i - 1], arr[i], arr[i + 1]
    denom = a + c - 2 * b
    if denom == 0:
        return float(i)
    return i + 0.5 * (a - c) / denom


def frequency_to_note(freq: float, a4_hz: float = 440.0) -> NoteReading:
    """Map a frequency to the nearest note name, octave, and cents offset."""
    midi = 69 + 12 * math.log2(freq / a4_hz)
    nearest = round(midi)
    cents = (midi - nearest) * 100.0
    name = NOTE_NAMES[nearest % 12]
    octave = nearest // 12 - 1
    return NoteReading(freq=freq, name=name, octave=octave, cents=cents)

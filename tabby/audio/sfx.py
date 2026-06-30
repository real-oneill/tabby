"""Load a WAV file into the mono float32 form the AudioEngine plays.

The output stream is mono at ``SAMPLE_RATE``; this downmixes stereo, normalizes to
[-1, 1], and linearly resamples if the file's rate differs."""

from __future__ import annotations

import wave

import numpy as np

from .engine import SAMPLE_RATE

_NORM = {1: 128.0, 2: 32768.0, 4: 2147483648.0}


def load_wav(path: str, target_rate: int = SAMPLE_RATE, peak: float | None = None) -> np.ndarray:
    """Return the WAV at ``path`` as mono float32 at ``target_rate``.

    If ``peak`` is given, the sample is scaled so its loudest point hits that level
    (handy for quietly-recorded clips)."""
    with wave.open(path, "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())

    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if width == 1:                       # 8-bit PCM is unsigned, centered at 128
        data = data - 128.0
    data /= _NORM[width]

    if channels > 1:                     # downmix to mono
        data = data.reshape(-1, channels).mean(axis=1)

    if rate != target_rate and len(data) > 1:
        n = int(round(len(data) * target_rate / rate))
        data = np.interp(np.linspace(0, len(data) - 1, n),
                         np.arange(len(data)), data).astype(np.float32)

    if peak is not None:
        loudest = float(np.abs(data).max())
        if loudest > 1e-4:
            data = data * (peak / loudest)

    return data.astype(np.float32)

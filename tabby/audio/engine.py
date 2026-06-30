"""Shared audio engine wrapping sounddevice.

Owns the microphone input stream (a ring buffer the tuner reads) and a persistent
output stream that mixes short one-shot samples (metronome clicks). Streams are
opened on demand so the tuner and metronome don't fight over the device.
"""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - sounddevice may fail to import w/o PortAudio
    sd = None

SAMPLE_RATE = 44100
_RING_SIZE = 8192


class AudioEngine:
    def __init__(self, config) -> None:
        self.config = config
        self.available = sd is not None

        # Input (mic) state
        self._in_stream = None
        self._ring = np.zeros(_RING_SIZE, dtype=np.float32)
        self._ring_lock = threading.Lock()

        # Output (clicks) state
        self._out_stream = None
        self._voices: list[list] = []  # each: [samples (np.float32), position int]
        self._voices_lock = threading.Lock()

        self.last_error: Optional[str] = None

    # --- Device listing (for Settings) ------------------------------------

    def list_devices(self, kind: str) -> list[tuple[int, str]]:
        """Return [(index, name)] for 'input' or 'output' devices."""
        if not self.available:
            return []
        out = []
        try:
            for idx, dev in enumerate(sd.query_devices()):
                channels = dev["max_input_channels"] if kind == "input" else dev["max_output_channels"]
                if channels > 0:
                    out.append((idx, dev["name"]))
        except Exception as exc:  # pragma: no cover
            self.last_error = str(exc)
        return out

    # --- Input (microphone) ----------------------------------------------

    def start_input(self) -> bool:
        if not self.available or self._in_stream is not None:
            return self._in_stream is not None
        try:
            self._in_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=1024,
                device=self.config.get("input_device"),
                callback=self._input_callback,
            )
            self._in_stream.start()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self._in_stream = None
            return False

    def stop_input(self) -> None:
        if self._in_stream is not None:
            try:
                self._in_stream.stop()
                self._in_stream.close()
            except Exception:
                pass
            self._in_stream = None

    def _input_callback(self, indata, frames, time_info, status):  # audio thread
        mono = indata[:, 0]
        with self._ring_lock:
            self._ring = np.roll(self._ring, -frames)
            self._ring[-frames:] = mono

    def read_window(self, size: int) -> np.ndarray:
        """Return the most recent `size` samples (zero-padded if not enough)."""
        size = min(size, _RING_SIZE)
        with self._ring_lock:
            return self._ring[-size:].copy()

    # --- Output (metronome clicks) ----------------------------------------

    def start_output(self) -> bool:
        if not self.available or self._out_stream is not None:
            return self._out_stream is not None
        try:
            self._out_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=2,            # stereo: the mono mix is copied to both speakers
                dtype="float32",
                blocksize=256,
                device=self.config.get("output_device"),
                callback=self._output_callback,
            )
            self._out_stream.start()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self._out_stream = None
            return False

    def stop_output(self) -> None:
        if self._out_stream is not None:
            try:
                self._out_stream.stop()
                self._out_stream.close()
            except Exception:
                pass
            self._out_stream = None
        with self._voices_lock:
            self._voices.clear()

    def play_sample(self, samples: np.ndarray) -> None:
        """Queue a one-shot sample to play immediately (non-blocking)."""
        with self._voices_lock:
            self._voices.append([samples.astype(np.float32), 0])

    def _output_callback(self, outdata, frames, time_info, status):  # audio thread
        mono = np.zeros(frames, dtype=np.float32)
        with self._voices_lock:
            still_active = []
            for voice in self._voices:
                samples, pos = voice
                end = pos + frames
                chunk = samples[pos:end]
                mono[: len(chunk)] += chunk
                voice[1] = end
                if end < len(samples):
                    still_active.append(voice)
            self._voices = still_active
        np.clip(mono, -1.0, 1.0, out=mono)
        outdata[:] = mono[:, None]   # duplicate the mono mix across all output channels

    # --- Lifecycle --------------------------------------------------------

    def close(self) -> None:
        self.stop_input()
        self.stop_output()

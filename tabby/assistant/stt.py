"""On-device speech-to-text via whisper.cpp (OSS), with graceful degradation.

Records a few seconds from the USB mic and transcribes locally on the Pi. If
whisper.cpp (pywhispercpp) or a model isn't available, `ready` is False and the
assistant shows setup guidance instead of crashing.

Model: set TABBY_WHISPER_MODEL to a ggml model name (e.g. "base.en") or a path.
"""

from __future__ import annotations

import os
import time

import numpy as np

try:
    import sounddevice as _sd
except Exception:  # noqa: BLE001
    _sd = None

_SAMPLE_RATE = 16000
_DEFAULT_MODEL = os.environ.get("TABBY_WHISPER_MODEL", "base.en")


class VoiceInput:
    def __init__(self, input_device=None, model: str | None = None) -> None:
        self.input_device = input_device
        self.model_name = model or _DEFAULT_MODEL
        self._model = None
        self._load_failed = False
        self._stream = None
        self._frames: list = []
        self._stream_rate = _SAMPLE_RATE

    @property
    def has_audio(self) -> bool:
        return _sd is not None

    # --- availability -----------------------------------------------------

    def _ensure_model(self):
        if self._model is not None or self._load_failed:
            return self._model
        try:
            from pywhispercpp.model import Model
            self._model = Model(self.model_name, print_realtime=False, print_progress=False)
        except Exception:  # noqa: BLE001 - missing lib or model
            self._load_failed = True
            self._model = None
        return self._model

    @property
    def ready(self) -> bool:
        return _sd is not None and self._ensure_model() is not None

    # --- capture + transcribe --------------------------------------------

    def _capture_rate(self) -> int:
        """16 kHz if the mic supports it, else the device's native rate (resampled)."""
        try:
            _sd.check_input_settings(device=self.input_device, samplerate=_SAMPLE_RATE, channels=1)
            return _SAMPLE_RATE
        except Exception:  # noqa: BLE001
            dev = self.input_device if self.input_device is not None else _sd.default.device[0]
            return int(_sd.query_devices(dev, "input")["default_samplerate"])

    # --- streaming capture (tap- or hold-to-talk) -------------------------

    _VOICE_RMS = 0.012   # above this counts as speech (for silence auto-stop)

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start_recording(self) -> None:
        if _sd is None:
            raise RuntimeError("no audio input library")
        self._stream_rate = self._capture_rate()
        self._frames = []
        self._t0 = time.monotonic()
        self._last_voice = self._t0
        self._stream = _sd.InputStream(samplerate=self._stream_rate, channels=1,
                                       dtype="float32", device=self.input_device, callback=self._on_block)
        self._stream.start()

    def _on_block(self, indata, frames, time_info, status) -> None:  # audio thread
        self._frames.append(indata.copy())
        if indata.size and float(np.sqrt(np.mean(indata ** 2))) > self._VOICE_RMS:
            self._last_voice = time.monotonic()

    def silence_elapsed(self) -> float:
        return time.monotonic() - self._last_voice if self._stream else 0.0

    def record_elapsed(self) -> float:
        return time.monotonic() - self._t0 if self._stream else 0.0

    def stop_recording(self) -> np.ndarray:
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self._frames, axis=0).reshape(-1)
        if self._stream_rate != _SAMPLE_RATE:
            n = int(len(audio) * _SAMPLE_RATE / self._stream_rate)
            audio = np.interp(np.linspace(0, len(audio), n, endpoint=False),
                              np.arange(len(audio)), audio).astype(np.float32)
        return audio

    def record(self, seconds: float) -> np.ndarray:
        if _sd is None:
            raise RuntimeError("no audio input library")
        rate = self._capture_rate()
        audio = _sd.rec(int(seconds * rate), samplerate=rate, channels=1,
                        dtype="float32", device=self.input_device)
        _sd.wait()
        audio = audio.reshape(-1)
        if rate != _SAMPLE_RATE:                      # whisper needs 16 kHz mono
            n = int(len(audio) * _SAMPLE_RATE / rate)
            audio = np.interp(np.linspace(0, len(audio), n, endpoint=False),
                              np.arange(len(audio)), audio).astype(np.float32)
        return audio

    def transcribe(self, audio: np.ndarray) -> str:
        model = self._ensure_model()
        if model is None:
            raise RuntimeError("speech model not available")
        segments = model.transcribe(audio.astype(np.float32))
        text = " ".join(getattr(s, "text", str(s)) for s in segments)
        return text.strip()

    def listen(self, seconds: float = 4.0) -> str:
        """Blocking: record then transcribe. Run this off the UI thread."""
        return self.transcribe(self.record(seconds))

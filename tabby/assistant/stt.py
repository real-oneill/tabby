"""On-device speech-to-text via whisper.cpp (OSS), with graceful degradation.

Records a few seconds from the USB mic and transcribes locally on the Pi. If
whisper.cpp (pywhispercpp) or a model isn't available, `ready` is False and the
assistant shows setup guidance instead of crashing.

Model: set TABBY_WHISPER_MODEL to a ggml model name (e.g. "base.en") or a path.
"""

from __future__ import annotations

import os

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

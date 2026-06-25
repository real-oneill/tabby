"""Shazam-style song identification from the mic, via shazamio (OSS).

Records a few seconds of ambient audio and asks Shazam what's playing. Unofficial /
personal-use (same posture as the Songsterr integration). Degrades gracefully if
shazamio or audio isn't available.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import wave

import numpy as np

try:
    import sounddevice as _sd
except Exception:  # noqa: BLE001
    _sd = None


class SongID:
    def __init__(self, input_device=None) -> None:
        self.input_device = input_device

    @property
    def available(self) -> bool:
        if _sd is None:
            return False
        try:
            import shazamio  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def _rate(self) -> int:
        dev = self.input_device if self.input_device is not None else _sd.default.device[0]
        try:
            return int(_sd.query_devices(dev, "input")["default_samplerate"])
        except Exception:  # noqa: BLE001
            return 44100

    def _record_wav(self, seconds: float) -> str:
        rate = self._rate()
        audio = _sd.rec(int(seconds * rate), samplerate=rate, channels=1,
                        dtype="float32", device=self.input_device)
        _sd.wait()
        pcm = (np.clip(audio.reshape(-1), -1.0, 1.0) * 32767).astype("<i2")
        path = tempfile.mktemp(suffix=".wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm.tobytes())
        return path

    def identify(self, seconds: float = 6.0) -> dict | None:
        """Return {'title','artist'} for what's playing, or None if unrecognized."""
        path = self._record_wav(seconds)
        try:
            from shazamio import Shazam
            shazam = Shazam()

            async def _run():
                fn = getattr(shazam, "recognize", None) or shazam.recognize_song
                return await fn(path)

            out = asyncio.run(_run())
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        track = (out or {}).get("track")
        if not track:
            return None
        images = track.get("images") or {}
        return {
            "title": track.get("title", ""),
            "artist": track.get("subtitle", ""),
            "art_url": images.get("coverarthq") or images.get("coverart") or "",
        }

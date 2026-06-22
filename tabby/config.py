"""Persisted user settings, stored as JSON in the user config dir."""

from __future__ import annotations

import json
import os
from typing import Any

_APP_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "tabby"
)
_CONFIG_PATH = os.path.join(_APP_DIR, "settings.json")

DEFAULTS: dict[str, Any] = {
    "input_device": None,    # None = system default; otherwise sounddevice index
    "output_device": None,
    "a4_hz": 440.0,          # tuning reference pitch
    "tempo": 120,            # metronome BPM
    "beats_per_measure": 4,  # metronome time signature numerator
    "accent_beat_one": True,
}


class Config:
    """Loads, holds, and saves settings. Access values via get()/set()."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            with open(_CONFIG_PATH, "r") as f:
                stored = json.load(f)
            # Keep only known keys; fall back to defaults for anything missing.
            for key in DEFAULTS:
                if key in stored:
                    self._data[key] = stored[key]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        try:
            os.makedirs(_APP_DIR, exist_ok=True)
            with open(_CONFIG_PATH, "w") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    def get(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

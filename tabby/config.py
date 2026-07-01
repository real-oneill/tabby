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
    "tabs_dir": "~/tabby-tabs",  # where the user drops their own .txt tabs
    "last_tab": None,            # path of the most recently opened tab
    "scroll_speed": 2.0,         # tab auto-scroll speed, lines/second
    "favorites": {"chord": [], "scale": [], "tab": []},  # starred items by id, per kind
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

    # --- favorites (starred chords / scales / tabs) -----------------------

    def favorites(self, kind: str) -> list:
        """Return the list of favorited ids for ``kind`` ('chord'|'scale'|'tab')."""
        return list((self._data.get("favorites") or {}).get(kind, []))

    def is_favorite(self, kind: str, item_id: str) -> bool:
        return item_id in (self._data.get("favorites") or {}).get(kind, [])

    def toggle_favorite(self, kind: str, item_id: str) -> bool:
        """Add/remove a favorite; returns the new state (True = now favorited)."""
        favs = dict(self._data.get("favorites") or {})
        ids = list(favs.get(kind, []))
        if item_id in ids:
            ids.remove(item_id)
            now = False
        else:
            ids.append(item_id)
            now = True
        favs[kind] = ids
        self.set("favorites", favs)
        return now

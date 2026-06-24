"""Tabby's own on-disk format for timed songs (so Songsterr tabs persist offline).

A ``.tabby`` file is compact JSON. Beats are stored as ``[start, duration, notes]``
with ``notes`` a list of ``[string, fret]`` pairs (empty = rest), keeping multi-track
songs reasonably small.
"""

from __future__ import annotations

import json
import os
import re

from .model import TimedBeat, TimedNote, TimedSong, TimedTrack

EXTENSION = ".tabby"
_FORMAT = "tabby-tab-1"


def to_dict(song: TimedSong) -> dict:
    return {
        "format": _FORMAT,
        "title": song.title,
        "artist": song.artist,
        "tempo": song.tempo,
        "default_track": song.default_track,
        "tracks": [
            {
                "name": t.name,
                "tuning": t.tuning,
                "beats": [[round(b.start, 4), round(b.duration, 4),
                           [[n.string, n.fret] for n in b.notes]] for b in t.beats],
            }
            for t in song.tracks
        ],
    }


def from_dict(d: dict) -> TimedSong:
    tracks = []
    for t in d.get("tracks", []):
        beats = [TimedBeat(start=b[0], duration=b[1],
                           notes=[TimedNote(string=n[0], fret=n[1]) for n in b[2]])
                 for b in t.get("beats", [])]
        tracks.append(TimedTrack(name=t.get("name", "TRACK"), tuning=t.get("tuning", []), beats=beats))
    return TimedSong(title=d.get("title", "?"), artist=d.get("artist", ""),
                    tempo=float(d.get("tempo", 120)), tracks=tracks,
                    default_track=int(d.get("default_track", 0)))


def load(path: str) -> TimedSong:
    with open(path, "r", encoding="utf-8") as f:
        return from_dict(json.load(f))


def _safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    return (name or "tab")[:80]


def save(song: TimedSong, directory: str) -> str | None:
    """Write ``song`` to ``directory`` as ``Artist - Title.tabby``.

    Skips if a file with that name already exists. Returns the path (or None).
    """
    directory = os.path.expanduser(directory)
    path = os.path.join(directory, _safe_name(song.display_name) + EXTENSION)
    if os.path.exists(path):
        return path
    try:
        os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(to_dict(song), f, separators=(",", ":"))
        return path
    except OSError:
        return None

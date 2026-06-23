"""Songsterr as a content source for the tempo-synced player.

Unauthenticated, plain HTTP (no browser needed):
  1. search:  GET /api/songs?pattern=...        -> songs (id, artist, title, tracks)
  2. meta:    GET /api/meta/{songId}            -> revisionId, image token, tracks
  3. notes:   GET {CDN}/{songId}/{revisionId}/{image}/{trackIndex}.json  (gzip)

The note JSON maps onto the timed model in model.py. Results are cached on disk
and requests are made politely (this is an unofficial, personal-use integration).
"""

from __future__ import annotations

import gzip
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .model import TimedBeat, TimedNote, TimedSong, TimedTrack

_API = "https://www.songsterr.com/api"
_CDN = "https://dqsljvtekg760.cloudfront.net"
_CACHE = os.path.expanduser("~/.cache/tabby/songsterr")
_UA = "Mozilla/5.0 (X11; Linux aarch64) Tabby/1.0 (+personal practice device)"
_TIMEOUT = 15
_MIN_INTERVAL = 0.34  # seconds between network requests (be polite)

_last_request = 0.0


@dataclass
class SongResult:
    song_id: int
    artist: str
    title: str
    has_player: bool

    @property
    def label(self) -> str:
        return f"{self.artist} - {self.title}"


@dataclass
class TrackInfo:
    index: int
    instrument: str
    name: str
    is_vocal: bool
    is_empty: bool


class SongsterrError(RuntimeError):
    pass


# --- HTTP + cache ---------------------------------------------------------

def _throttle() -> None:
    global _last_request
    wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _fetch(url: str) -> bytes:
    _throttle()
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except Exception as exc:  # network, HTTP error, timeout
        raise SongsterrError(str(exc)) from exc
    if raw[:2] == b"\x1f\x8b":  # gzip magic
        raw = gzip.decompress(raw)
    return raw


def _cached(key: str, url: str) -> bytes:
    path = os.path.join(_CACHE, key)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    data = _fetch(url)
    try:
        os.makedirs(_CACHE, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    except OSError:
        pass
    return data


# --- public API -----------------------------------------------------------

def search(pattern: str, size: int = 20) -> list[SongResult]:
    if not pattern.strip():
        return []
    url = f"{_API}/songs?pattern={urllib.parse.quote(pattern)}&size={size}"
    data = json.loads(_fetch(url))  # search is live (not cached)
    out = []
    for s in data:
        if not isinstance(s, dict) or "songId" not in s:
            continue
        out.append(SongResult(song_id=s["songId"], artist=s.get("artist", "?"),
                              title=s.get("title", "?"), has_player=bool(s.get("hasPlayer"))))
    return out


def meta(song_id: int) -> dict:
    return json.loads(_cached(f"meta_{song_id}.json", f"{_API}/meta/{song_id}"))


def tracks(song_id: int) -> list[TrackInfo]:
    m = meta(song_id)
    out = []
    for i, t in enumerate(m.get("tracks", [])):
        out.append(TrackInfo(index=i, instrument=t.get("instrument", "?"),
                            name=t.get("name", t.get("instrument", "?")),
                            is_vocal=bool(t.get("isVocalTrack")), is_empty=bool(t.get("isEmpty"))))
    return out


def default_track_index(song_id: int) -> int:
    m = meta(song_id)
    for key in ("popularTrackGuitar", "defaultTrack", "popularTrack"):
        v = m.get(key)
        if isinstance(v, int):
            return v
    return 0


def load_song(song_id: int, track_index: int) -> TimedSong:
    """Fetch one track's notes and build a single-track timed song."""
    m = meta(song_id)
    rev = m["revisionId"]
    image = m["image"]
    url = f"{_CDN}/{song_id}/{rev}/{image}/{track_index}.json"
    part = json.loads(_cached(f"part_{song_id}_{rev}_{track_index}.json", url))
    track = _map_part(part)
    return TimedSong(title=m.get("title", "?"), artist=m.get("artist", ""),
                    tempo=_base_tempo(part), tracks=[track])


# --- mapping --------------------------------------------------------------

def _base_tempo(part: dict) -> float:
    changes = (part.get("automations") or {}).get("tempo") or []
    if changes:
        return float(changes[0].get("bpm", 120))
    return 120.0


def _map_part(part: dict) -> TimedTrack:
    tuning = part.get("tuning") or [64, 59, 55, 50, 45, 40]
    beats: list[TimedBeat] = []
    pos = 0.0
    for measure in part.get("measures", []):
        voices = measure.get("voices") or []
        if not voices:
            continue
        for beat in voices[0].get("beats", []):
            num, den = beat.get("duration", [1, 4])
            qn = (num / den) * 4.0 if den else 1.0
            raw_notes = beat.get("notes") or []
            if beat.get("rest") or all(n.get("rest") for n in raw_notes):
                notes: list[TimedNote] = []
            else:
                notes = [TimedNote(string=n["string"], fret=n["fret"])
                         for n in raw_notes if not n.get("rest") and "string" in n]
            beats.append(TimedBeat(start=pos, duration=qn, notes=notes))
            pos += qn
    name = part.get("name") or part.get("instrument") or "TRACK"
    return TimedTrack(name=name, tuning=tuning, beats=beats)

"""Build in-memory ``TimedSong``s from chords/scales so the existing synced player
and ``render_synced`` can play them back — no new playback code needed."""

from __future__ import annotations

from ..tabs.model import TimedBeat, TimedNote, TimedSong, TimedTrack
from .library import DEFAULT_BPM, MUTED, STANDARD_TUNING, Chord, ChordPosition, Scale, ScalePosition


def _wrap(name: str, beats: list[TimedBeat], tempo: float) -> TimedSong:
    track = TimedTrack(name, list(STANDARD_TUNING), beats)
    return TimedSong(name, "", tempo, [track], 0)


def scale_song(scale: Scale, position: ScalePosition, tempo: float = DEFAULT_BPM,
               descend: bool = True) -> TimedSong:
    """One note per beat, ascending the box; append the descent when ``descend``."""
    seq = list(position.sequence)
    if descend:
        seq = seq + list(reversed(seq))
    beats = [TimedBeat(float(i), 1.0, [TimedNote(s, f)]) for i, (s, f) in enumerate(seq)]
    beats.append(TimedBeat(float(len(seq)), 1.0, []))   # trailing rest so the end isn't clipped
    return _wrap(scale.name, beats, tempo)


def chord_song(chord: Chord, position: ChordPosition, mode: str = "arpeggio",
               tempo: float = DEFAULT_BPM, repeats: int = 4) -> TimedSong:
    """``strum`` = all notes hit together each beat; ``arpeggio`` = one note per beat low->high.

    Open strings (fret 0) sound; muted strings are skipped."""
    played = [(h.string, h.fret) for h in position.hits if h.fret != MUTED]
    if mode == "strum":
        block = [TimedNote(s, f) for s, f in played]
        beats = [TimedBeat(float(r), 1.0, list(block)) for r in range(repeats)]
        beats.append(TimedBeat(float(repeats), 1.0, []))
    else:  # arpeggio, low string (6) -> high string (1)
        ordered = sorted(played, key=lambda sf: -sf[0])
        beats = [TimedBeat(float(i), 1.0, [TimedNote(s, f)]) for i, (s, f) in enumerate(ordered)]
        beats.append(TimedBeat(float(len(ordered)), 1.0, []))
    return _wrap(chord.name, beats, tempo)

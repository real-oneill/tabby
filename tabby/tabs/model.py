"""Timed tab model for tempo-synced playback (Guitar Pro / Songsterr).

Positions and durations are in *quarter-note beats* from the start of the track, so
playback can scale tempo freely and the renderer can place beats on a time axis
independent of the source format.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TimedNote:
    string: int   # 1 = highest (thin) string ... N = lowest, GP convention
    fret: int


@dataclass
class TimedBeat:
    start: float              # quarter-note beats from track start
    duration: float           # length in quarter-note beats
    notes: list[TimedNote] = field(default_factory=list)

    @property
    def is_rest(self) -> bool:
        return not self.notes


@dataclass
class TimedTrack:
    name: str
    tuning: list[int]         # MIDI pitch per string, index 0 = string 1 (high)
    beats: list[TimedBeat] = field(default_factory=list)

    @property
    def string_count(self) -> int:
        return len(self.tuning)

    @property
    def total_beats(self) -> float:
        if not self.beats:
            return 0.0
        last = self.beats[-1]
        return last.start + last.duration


@dataclass
class TimedSong:
    title: str
    artist: str
    tempo: float             # base BPM (quarter notes per minute)
    tracks: list[TimedTrack] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title

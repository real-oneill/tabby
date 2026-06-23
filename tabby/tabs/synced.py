"""Tempo-synced playback cursor for the timed model: play, slow-down, A/B loop.

The cursor position is in quarter-note beats; ``update(dt)`` advances it at
``tempo * rate`` quarter-notes per minute. ``rate`` is the practice slow-down
(1.0 = full speed). No background thread — it steps in the screen's update loop.
"""

from __future__ import annotations

import bisect

RATE_MIN = 0.25
RATE_MAX = 1.0
RATE_STEP = 0.25


class SyncedPlayer:
    def __init__(self, song, track_index: int = 0, rate: float = 1.0) -> None:
        self.song = song
        self.track_index = max(0, min(track_index, len(song.tracks) - 1))
        self.rate = self._clamp_rate(rate)
        self.pos = 0.0
        self.playing = False
        self.loop_a: float | None = None
        self.loop_b: float | None = None

    # --- queries ----------------------------------------------------------

    @property
    def track(self):
        return self.song.tracks[self.track_index]

    @property
    def tempo(self) -> float:
        return self.song.tempo

    @property
    def total(self) -> float:
        return max(self.track.total_beats, 1e-6)

    @property
    def loop_active(self) -> bool:
        return self.loop_a is not None and self.loop_b is not None

    def current_beat_index(self) -> int:
        """Index of the beat the cursor is currently inside (-1 if none)."""
        beats = self.track.beats
        if not beats:
            return -1
        starts = [b.start for b in beats]
        i = bisect.bisect_right(starts, self.pos) - 1
        return max(0, i)

    # --- transport --------------------------------------------------------

    def toggle(self) -> None:
        if self.pos >= self.total:
            self.pos = 0.0
        self.playing = not self.playing

    def faster(self) -> None:
        self.rate = self._clamp_rate(self.rate + RATE_STEP)

    def slower(self) -> None:
        self.rate = self._clamp_rate(self.rate - RATE_STEP)

    def to_start(self) -> None:
        self.pos = self.loop_a if self.loop_active else 0.0

    def scrub(self, d_beats: float) -> None:
        self.pos = self._clamp_pos(self.pos + d_beats)

    def set_a(self) -> None:
        # Tapping A when a full loop exists clears it; otherwise (re)starts one.
        if self.loop_active:
            self.loop_a = self.loop_b = None
        else:
            self.loop_a = self.pos
            self.loop_b = None

    def set_b(self) -> None:
        if self.loop_a is not None and self.pos > self.loop_a:
            self.loop_b = self.pos

    def cycle_track(self) -> None:
        if len(self.song.tracks) > 1:
            self.track_index = (self.track_index + 1) % len(self.song.tracks)
            self.pos = self._clamp_pos(self.pos)
            self.loop_a = self.loop_b = None

    # --- tick -------------------------------------------------------------

    def update(self, dt: float) -> None:
        if not self.playing:
            return
        self.pos += (self.tempo * self.rate / 60.0) * dt
        if self.loop_active and self.pos >= self.loop_b:
            self.pos = self.loop_a
        elif self.pos >= self.total:
            self.pos = self.total
            self.playing = False

    # --- helpers ----------------------------------------------------------

    def _clamp_pos(self, v: float) -> float:
        return max(0.0, min(self.total, v))

    @staticmethod
    def _clamp_rate(v: float) -> float:
        return max(RATE_MIN, min(RATE_MAX, round(v, 2)))

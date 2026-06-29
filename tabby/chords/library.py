"""Preloaded chord & scale data.

String numbering matches the timed model's ``TimedNote``: **1 = high E (thin) ...
6 = low E (thick)**. A fret is the absolute fret number; 0 = open, ``MUTED`` = not
played. Shapes below are written in the natural "chord chart" order — low E first —
and ``_chord_pos`` flips that to string numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MUTED = -1
# MIDI pitch per string, index 0 = string 1 (high E). Matches the tabs model.
STANDARD_TUNING = [64, 59, 55, 50, 45, 40]
DEFAULT_BPM = 80.0


@dataclass
class StringHit:
    string: int        # 1..6 (1 = high E)
    fret: int          # absolute fret; 0 = open; MUTED = not played
    finger: int = 0    # 0 = none/open, 1..4 = fretting finger (chords only)


@dataclass
class ChordPosition:
    label: str                              # "OPEN", "12TH FRET", "BARRE (E-SHAPE)"
    base_fret: int                          # fret of the diagram's top fret row
    hits: list[StringHit]                   # exactly 6, one per string
    barre: tuple[int, int, int] | None = None  # (finger, from_string, to_string)


@dataclass
class Chord:
    name: str
    category: str                           # "open" | "barre" | "7th" | "9th"
    positions: list[ChordPosition]


@dataclass
class ScalePosition:
    label: str                              # "OPEN POSITION", "5TH FRET"
    fret_lo: int                            # lowest fret rendered (0 includes the nut)
    fret_hi: int                            # highest fret rendered
    hits: list[StringHit]                   # all scale tones in this box
    roots: set[tuple[int, int]]             # (string, fret) pairs that are the root
    sequence: list[tuple[int, int]] = field(default_factory=list)  # ascending play-along


@dataclass
class Scale:
    name: str
    root: str
    kind: str                               # "min_pent" | "maj_pent" | "major" | "mixolydian"
    positions: list[ScalePosition]


# --- builders -------------------------------------------------------------

def _chord_pos(label, base_fret, frets, fingers, barre=None) -> ChordPosition:
    """``frets``/``fingers`` are 6 entries in low-E -> high-E order (string 6..1)."""
    hits = [StringHit(string=6 - i, fret=fr, finger=fg)
            for i, (fr, fg) in enumerate(zip(frets, fingers))]
    return ChordPosition(label=label, base_fret=base_fret, hits=hits, barre=barre)


def _scale_pos(label, fret_lo, fret_hi, per_string, roots) -> ScalePosition:
    """``per_string``: {string(1..6): [frets]}. Sequence ascends string 6 -> 1, low fret first."""
    hits = [StringHit(string=s, fret=f)
            for s in range(1, 7) for f in per_string.get(s, [])]
    sequence = [(s, f) for s in range(6, 0, -1) for f in sorted(per_string.get(s, []))]
    return ScalePosition(label, fret_lo, fret_hi, hits, set(roots), sequence)


# --- chords ---------------------------------------------------------------

CHORDS: list[Chord] = [
    Chord("E MAJOR", "open", [
        _chord_pos("OPEN", 1, [0, 2, 2, 1, 0, 0], [0, 2, 3, 1, 0, 0]),
        _chord_pos("12TH FRET", 12, [12, 14, 14, 13, 12, 12], [1, 3, 4, 2, 1, 1],
                   barre=(1, 6, 1)),
    ]),
    Chord("E MINOR", "open", [
        _chord_pos("OPEN", 1, [0, 2, 2, 0, 0, 0], [0, 2, 3, 0, 0, 0]),
    ]),
    Chord("A MAJOR", "open", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 2, 2, 0], [0, 0, 1, 2, 3, 0]),
    ]),
    Chord("A MINOR", "open", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 2, 1, 0], [0, 0, 2, 3, 1, 0]),
    ]),
    Chord("D MAJOR", "open", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 3, 2], [0, 0, 0, 1, 3, 2]),
    ]),
    Chord("D MINOR", "open", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 3, 1], [0, 0, 0, 2, 3, 1]),
    ]),
    Chord("G MAJOR", "open", [
        _chord_pos("OPEN", 1, [3, 2, 0, 0, 0, 3], [2, 1, 0, 0, 0, 3]),
    ]),
    Chord("C MAJOR", "open", [
        _chord_pos("OPEN", 1, [MUTED, 3, 2, 0, 1, 0], [0, 3, 2, 0, 1, 0]),
    ]),
    Chord("F MAJOR", "barre", [
        _chord_pos("BARRE (E-SHAPE)", 1, [1, 3, 3, 2, 1, 1], [1, 3, 4, 2, 1, 1],
                   barre=(1, 6, 1)),
    ]),
    Chord("B MAJOR", "barre", [
        _chord_pos("BARRE (A-SHAPE)", 2, [MUTED, 2, 4, 4, 4, 2], [0, 1, 3, 3, 3, 1],
                   barre=(1, 5, 1)),
    ]),
    Chord("E7", "7th", [
        _chord_pos("OPEN", 1, [0, 2, 0, 1, 0, 0], [0, 2, 0, 1, 0, 0]),
    ]),
    Chord("A7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 0, 2, 0], [0, 0, 2, 0, 3, 0]),
    ]),
    Chord("B7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 2, 1, 2, 0, 2], [0, 2, 1, 3, 0, 4]),
    ]),
    Chord("D7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 1, 2], [0, 0, 0, 2, 1, 3]),
    ]),
    Chord("E9", "9th", [
        # Movable funk/blues 9th, root on the A string at the 7th fret.
        _chord_pos("7TH FRET", 6, [MUTED, 7, 6, 7, 7, 7], [0, 2, 1, 3, 4, 4]),
    ]),
    Chord("A9", "9th", [
        # Movable 9th with root on the low-E string at the 5th fret.
        _chord_pos("5TH FRET", 5, [5, 7, 5, 6, 5, MUTED], [1, 3, 1, 2, 1, 0]),
    ]),
]


# --- scales ---------------------------------------------------------------

SCALES: list[Scale] = [
    Scale("E MINOR PENTATONIC", "E", "min_pent", [
        _scale_pos("OPEN POSITION", 0, 3,
                   {6: [0, 3], 5: [0, 2], 4: [0, 2], 3: [0, 2], 2: [0, 3], 1: [0, 3]},
                   roots={(6, 0), (4, 2), (1, 0)}),
    ]),
    Scale("A MINOR PENTATONIC", "A", "min_pent", [
        _scale_pos("5TH FRET", 5, 8,
                   {6: [5, 8], 5: [5, 7], 4: [5, 7], 3: [5, 7], 2: [5, 8], 1: [5, 8]},
                   roots={(6, 5), (4, 7), (1, 5)}),
    ]),
    Scale("A MAJOR PENTATONIC", "A", "maj_pent", [
        _scale_pos("2ND FRET", 2, 5,
                   {6: [2, 5], 5: [2, 4], 4: [2, 4], 3: [2, 4], 2: [2, 5], 1: [2, 5]},
                   roots={(6, 5), (3, 2), (1, 5)}),
    ]),
    Scale("C MAJOR", "C", "major", [
        _scale_pos("OPEN POSITION", 0, 3,
                   {6: [0, 1, 3], 5: [0, 2, 3], 4: [0, 2, 3], 3: [0, 2], 2: [0, 1, 3], 1: [0, 1, 3]},
                   roots={(5, 3), (2, 1)}),
    ]),
    Scale("G MIXOLYDIAN", "G", "mixolydian", [
        # Same open-position note pool as C major, rooted on G (the b7 mode of C).
        _scale_pos("OPEN POSITION", 0, 3,
                   {6: [0, 1, 3], 5: [0, 2, 3], 4: [0, 2, 3], 3: [0, 2], 2: [0, 1, 3], 1: [0, 1, 3]},
                   roots={(6, 3), (3, 0), (1, 3)}),
    ]),
]


# --- lookup ---------------------------------------------------------------

def find_by_name(name: str):
    """Case/space-insensitive lookup over chords then scales. Returns (kind, item) or None.

    Matches exact name, then a normalized substring (so "E major" finds "E MAJOR" and
    "e min pent" finds "E MINOR PENTATONIC")."""
    def norm(s: str) -> str:
        return "".join(ch for ch in s.lower() if ch.isalnum())

    target = norm(name)
    if not target:
        return None
    items = [("chord", c) for c in CHORDS] + [("scale", s) for s in SCALES]
    for kind, item in items:
        if norm(item.name) == target:
            return (kind, item)
    for kind, item in items:
        if target in norm(item.name) or norm(item.name) in target:
            return (kind, item)
    return None

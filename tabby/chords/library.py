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
    # --- power (5th) chords: root + fifth (+ octave), rest muted ---
    Chord("E5", "5th", [
        _chord_pos("OPEN", 1, [0, 2, 2, MUTED, MUTED, MUTED], [0, 1, 1, 0, 0, 0]),
    ]),
    Chord("A5", "5th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 2, MUTED, MUTED], [0, 0, 1, 1, 0, 0]),
    ]),
    Chord("D5", "5th", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 3, MUTED], [0, 0, 0, 1, 3, 0]),
    ]),
    Chord("F5", "5th", [
        _chord_pos("1ST FRET", 1, [1, 3, 3, MUTED, MUTED, MUTED], [1, 3, 4, 0, 0, 0]),
    ]),
    Chord("B5", "5th", [
        _chord_pos("2ND FRET", 1, [MUTED, 2, 4, 4, MUTED, MUTED], [0, 1, 3, 4, 0, 0]),
    ]),
    Chord("C5", "5th", [
        _chord_pos("3RD FRET", 1, [MUTED, 3, 5, 5, MUTED, MUTED], [0, 1, 3, 4, 0, 0]),
    ]),
    Chord("G5", "5th", [
        _chord_pos("3RD FRET", 1, [3, 5, 5, MUTED, MUTED, MUTED], [1, 3, 4, 0, 0, 0]),
    ]),
    # --- dominant 7ths ---
    Chord("E7", "7th", [
        _chord_pos("OPEN", 1, [0, 2, 0, 1, 0, 0], [0, 2, 0, 1, 0, 0]),
    ]),
    Chord("A7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 0, 2, 0], [0, 0, 2, 0, 3, 0]),
    ]),
    Chord("B7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 2, 1, 2, 0, 2], [0, 2, 1, 3, 0, 4]),
    ]),
    Chord("C7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 3, 2, 3, 1, 0], [0, 3, 2, 4, 1, 0]),
    ]),
    Chord("D7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 1, 2], [0, 0, 0, 2, 1, 3]),
    ]),
    Chord("F7", "7th", [
        _chord_pos("BARRE (E-SHAPE)", 1, [1, 3, 1, 2, 1, 1], [1, 3, 1, 2, 1, 1], barre=(1, 6, 1)),
    ]),
    Chord("G7", "7th", [
        _chord_pos("OPEN", 1, [3, 2, 0, 0, 0, 1], [3, 2, 0, 0, 0, 1]),
    ]),
    # --- minor 7ths ---
    Chord("A MINOR 7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 0, 1, 0], [0, 0, 2, 0, 1, 0]),
    ]),
    Chord("B MINOR 7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 2, 0, 2, 0, 2], [0, 2, 0, 3, 0, 4]),
    ]),
    Chord("D MINOR 7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 1, 1], [0, 0, 0, 2, 1, 1]),
    ]),
    Chord("E MINOR 7", "7th", [
        _chord_pos("OPEN", 1, [0, 2, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0]),
    ]),
    # --- major 7ths ---
    Chord("A MAJOR 7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 1, 2, 0], [0, 0, 2, 1, 3, 0]),
    ]),
    Chord("C MAJOR 7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 3, 2, 0, 0, 0], [0, 3, 2, 0, 0, 0]),
    ]),
    Chord("D MAJOR 7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 2, 2], [0, 0, 0, 1, 1, 1], barre=(1, 3, 1)),
    ]),
    Chord("E MAJOR 7", "7th", [
        _chord_pos("OPEN", 1, [0, 2, 1, 1, 0, 0], [0, 3, 1, 2, 0, 0]),
    ]),
    Chord("F MAJOR 7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 3, 2, 1, 0], [0, 0, 3, 2, 1, 0]),
    ]),
    Chord("G MAJOR 7", "7th", [
        _chord_pos("OPEN", 1, [3, 2, 0, 0, 0, 2], [3, 2, 0, 0, 0, 1]),
    ]),
    # --- dominant 9ths (open voicings) ---
    Chord("E9", "9th", [
        _chord_pos("OPEN", 1, [0, 2, 0, 1, 0, 2], [0, 2, 0, 1, 0, 3]),
    ]),
    Chord("A9", "9th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 4, 2, 3], [0, 0, 1, 4, 2, 3]),
    ]),
    Chord("B9", "9th", [
        _chord_pos("OPEN", 1, [MUTED, 2, 1, 2, 2, 2], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1)),
    ]),
    Chord("C9", "9th", [
        _chord_pos("OPEN", 1, [MUTED, 3, 2, 3, 3, 3], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1)),
    ]),
    Chord("D9", "9th", [
        _chord_pos("5TH FRET", 4, [MUTED, 5, 4, 5, 5, 5], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1)),
    ]),
    Chord("G9", "9th", [
        _chord_pos("3RD FRET", 3, [3, 5, 3, 4, 3, 5], [1, 3, 1, 2, 1, 4], barre=(1, 6, 2)),
    ]),
]


# --- scales ---------------------------------------------------------------

SCALES: list[Scale] = [
    Scale("E MINOR PENTATONIC", "E", "min_pent", [
        # Three shapes up the neck: open box, 2nd-fret box, and the open shape an octave up.
        _scale_pos("OPEN POSITION", 0, 3,
                   {6: [0, 3], 5: [0, 2], 4: [0, 2], 3: [0, 2], 2: [0, 3], 1: [0, 3]},
                   roots={(6, 0), (4, 2), (1, 0)}),
        _scale_pos("2ND FRET", 2, 5,
                   {6: [3, 5], 5: [2, 5], 4: [2, 5], 3: [2, 4], 2: [3, 5], 1: [3, 5]},
                   roots={(4, 2), (2, 5)}),
        _scale_pos("12TH FRET", 12, 15,
                   {6: [12, 15], 5: [12, 14], 4: [12, 14], 3: [12, 14], 2: [12, 15], 1: [12, 15]},
                   roots={(6, 12), (4, 14), (1, 12)}),
    ]),
    Scale("A MINOR PENTATONIC", "A", "min_pent", [
        # Open box, the classic 5th-fret box, and the 7th-fret box.
        _scale_pos("OPEN POSITION", 0, 3,
                   {6: [0, 3], 5: [0, 3], 4: [0, 2], 3: [0, 2], 2: [1, 3], 1: [0, 3]},
                   roots={(5, 0), (3, 2)}),
        _scale_pos("5TH FRET", 5, 8,
                   {6: [5, 8], 5: [5, 7], 4: [5, 7], 3: [5, 7], 2: [5, 8], 1: [5, 8]},
                   roots={(6, 5), (4, 7), (1, 5)}),
        _scale_pos("7TH FRET", 7, 10,
                   {6: [8, 10], 5: [7, 10], 4: [7, 10], 3: [7, 9], 2: [8, 10], 1: [8, 10]},
                   roots={(4, 7), (2, 10)}),
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
    Scale("A MIXOLYDIAN", "A", "mixolydian", [
        # A B C# D E F# G, open position.
        _scale_pos("OPEN POSITION", 0, 3,
                   {6: [0, 2, 3], 5: [0, 2], 4: [0, 2], 3: [0, 2], 2: [0, 2, 3], 1: [0, 2, 3]},
                   roots={(5, 0), (3, 2)}),
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

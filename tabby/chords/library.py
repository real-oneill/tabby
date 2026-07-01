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
    barre: tuple[int, int, int, int] | None = None  # (finger, from_string, to_string, fret)


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


def _ordinal(n: int) -> str:
    suffix = "TH" if 10 <= n % 100 <= 20 else {1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH")
    return f"{n}{suffix} FRET"


# Pitch class of each root name; semitone sets for each scale type.
_PITCH = {"C": 0, "C#": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6,
          "G": 7, "G#": 8, "A": 9, "Bb": 10, "B": 11}
_SCALE_INTERVALS = {
    "min_pent": {0, 3, 5, 7, 10},
    "maj_pent": {0, 2, 4, 7, 9},
    "major": {0, 2, 4, 5, 7, 9, 11},
    "mixolydian": {0, 2, 4, 5, 7, 9, 10},
}
# Notes per string for each scale type: pentatonics 2, seven-note scales 3.
_NPS = {"min_pent": 2, "maj_pent": 2, "major": 3, "mixolydian": 3}


def _gen_scale(name: str, root: str, kind: str, lo_max: int = 12) -> Scale:
    """Build every neck position of a scale as an n-notes-per-string box (2 for
    pentatonics, 3 for diatonic). One position per scale-tone on the low-E string:
    the ascending scale is dealt out n notes to a string, giving even, play-along
    friendly runs and the recognizable CAGED / 3-nps shapes. Cycle them like chords."""
    root_pc = _PITCH[root]
    intervals = _SCALE_INTERVALS[kind]
    n = _NPS[kind]

    def is_tone(midi: int) -> bool:
        return (midi - root_pc) % 12 in intervals

    starts = [f for f in range(0, lo_max) if is_tone(STANDARD_TUNING[5] + f)]
    positions = []
    for f0 in starts:
        # Ascending scale pitches from low-E+f0, dealt n-per-string (string 6 first).
        pitches: list[int] = []
        p = STANDARD_TUNING[5] + f0
        while len(pitches) < 6 * n:
            if is_tone(p):
                pitches.append(p)
            p += 1
        per_string: dict[int, list[int]] = {}
        roots: set[tuple[int, int]] = set()
        for i in range(6):
            s = 6 - i                      # i=0 -> low E (string 6) ... i=5 -> high E
            for j in range(n):
                pitch = pitches[i * n + j]
                fret = pitch - STANDARD_TUNING[s - 1]
                per_string.setdefault(s, []).append(fret)
                if (pitch - root_pc) % 12 == 0:
                    roots.add((s, fret))
        frets = [f for fs in per_string.values() for f in fs]
        if min(frets) < 0:
            continue   # this shape isn't playable that low; it appears higher up the neck
        label = "OPEN POSITION" if f0 == 0 else _ordinal(f0)
        positions.append(_scale_pos(label, min(frets), max(frets), per_string, roots))
    return Scale(name, root, kind, positions)


# Movable CAGED barre shapes (root on the 6th string = E-shape, on the 5th = A-shape),
# so the open triads can also be played up the neck.
def _e_major(r): return _chord_pos(_ordinal(r), r, [r, r + 2, r + 2, r + 1, r, r], [1, 3, 4, 2, 1, 1], barre=(1, 6, 1, r))
def _a_major(r): return _chord_pos(_ordinal(r), r, [MUTED, r, r + 2, r + 2, r + 2, r], [0, 1, 3, 3, 3, 1], barre=(1, 5, 1, r))
def _e_minor(r): return _chord_pos(_ordinal(r), r, [r, r + 2, r + 2, r, r, r], [1, 3, 4, 1, 1, 1], barre=(1, 6, 1, r))
def _a_minor(r): return _chord_pos(_ordinal(r), r, [MUTED, r, r + 2, r + 2, r + 1, r], [0, 1, 3, 4, 2, 1], barre=(1, 5, 1, r))


# --- chords ---------------------------------------------------------------

CHORDS: list[Chord] = [
    Chord("E MAJOR", "open", [
        _chord_pos("OPEN", 1, [0, 2, 2, 1, 0, 0], [0, 2, 3, 1, 0, 0]),
        _chord_pos("12TH FRET", 12, [12, 14, 14, 13, 12, 12], [1, 3, 4, 2, 1, 1],
                   barre=(1, 6, 1, 12)),
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
    Chord("Bb MINOR", "barre", [
        _chord_pos("BARRE (Am-SHAPE)", 1, [MUTED, 1, 3, 3, 2, 1], [0, 1, 3, 4, 2, 1], barre=(1, 5, 1, 1)),
    ]),
    Chord("Eb MINOR", "barre", [
        _chord_pos("BARRE (Am-SHAPE)", 6, [MUTED, 6, 8, 8, 7, 6], [0, 1, 3, 4, 2, 1], barre=(1, 5, 1, 6)),
    ]),
    Chord("G MAJOR", "open", [
        _chord_pos("OPEN", 1, [3, 2, 0, 0, 0, 3], [2, 1, 0, 0, 0, 3]),
    ]),
    Chord("C MAJOR", "open", [
        _chord_pos("OPEN", 1, [MUTED, 3, 2, 0, 1, 0], [0, 3, 2, 0, 1, 0]),
    ]),
    Chord("F MAJOR", "barre", [
        _chord_pos("BARRE (E-SHAPE)", 1, [1, 3, 3, 2, 1, 1], [1, 3, 4, 2, 1, 1],
                   barre=(1, 6, 1, 1)),
    ]),
    Chord("B MAJOR", "barre", [
        _chord_pos("BARRE (A-SHAPE)", 2, [MUTED, 2, 4, 4, 4, 2], [0, 1, 3, 3, 3, 1],
                   barre=(1, 5, 1, 2)),
    ]),
    # --- flat major chords (movable barre shapes) ---
    Chord("Bb MAJOR", "barre", [
        _chord_pos("BARRE (A-SHAPE)", 1, [MUTED, 1, 3, 3, 3, 1], [0, 1, 3, 3, 3, 1], barre=(1, 5, 1, 1)),
    ]),
    Chord("Db MAJOR", "barre", [
        _chord_pos("BARRE (A-SHAPE)", 4, [MUTED, 4, 6, 6, 6, 4], [0, 1, 3, 3, 3, 1], barre=(1, 5, 1, 4)),
    ]),
    Chord("Eb MAJOR", "barre", [
        _chord_pos("BARRE (A-SHAPE)", 6, [MUTED, 6, 8, 8, 8, 6], [0, 1, 3, 3, 3, 1], barre=(1, 5, 1, 6)),
    ]),
    Chord("Gb MAJOR", "barre", [
        _chord_pos("BARRE (E-SHAPE)", 2, [2, 4, 4, 3, 2, 2], [1, 3, 4, 2, 1, 1], barre=(1, 6, 1, 2)),
    ]),
    Chord("Ab MAJOR", "barre", [
        _chord_pos("BARRE (E-SHAPE)", 4, [4, 6, 6, 5, 4, 4], [1, 3, 4, 2, 1, 1], barre=(1, 6, 1, 4)),
    ]),
    # --- power (5th) chords: root + fifth (+ octave), rest muted ---
    Chord("E5", "5th", [
        _chord_pos("OPEN", 1, [0, 2, 2, MUTED, MUTED, MUTED], [0, 1, 1, 0, 0, 0]),
        _chord_pos("7TH FRET", 7, [MUTED, 7, 9, 9, MUTED, MUTED], [0, 1, 3, 4, 0, 0]),
    ]),
    Chord("A5", "5th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 2, MUTED, MUTED], [0, 0, 1, 1, 0, 0]),
        _chord_pos("5TH FRET", 5, [5, 7, 7, MUTED, MUTED, MUTED], [1, 3, 4, 0, 0, 0]),
    ]),
    Chord("D5", "5th", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 3, MUTED], [0, 0, 0, 1, 3, 0]),
        _chord_pos("5TH FRET", 5, [MUTED, 5, 7, 7, MUTED, MUTED], [0, 1, 3, 4, 0, 0]),
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
        _chord_pos("7TH FRET", 7, [MUTED, 7, 9, 7, 9, 7], [0, 1, 3, 1, 4, 1], barre=(1, 5, 1, 7)),
    ]),
    Chord("A7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 0, 2, 0], [0, 0, 2, 0, 3, 0]),
        _chord_pos("5TH FRET", 5, [5, 7, 5, 6, 5, 5], [1, 3, 1, 2, 1, 1], barre=(1, 6, 1, 5)),
    ]),
    Chord("B7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 2, 1, 2, 0, 2], [0, 2, 1, 3, 0, 4]),
    ]),
    Chord("C7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, 3, 2, 3, 1, 0], [0, 3, 2, 4, 1, 0]),
    ]),
    Chord("D7", "7th", [
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 1, 2], [0, 0, 0, 2, 1, 3]),
        _chord_pos("5TH FRET", 5, [MUTED, 5, 7, 5, 7, 5], [0, 1, 3, 1, 4, 1], barre=(1, 5, 1, 5)),
    ]),
    Chord("F7", "7th", [
        _chord_pos("BARRE (E-SHAPE)", 1, [1, 3, 1, 2, 1, 1], [1, 3, 1, 2, 1, 1], barre=(1, 6, 1, 1)),
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
        _chord_pos("OPEN", 1, [MUTED, MUTED, 0, 2, 2, 2], [0, 0, 0, 1, 1, 1], barre=(1, 3, 1, 2)),
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
    # --- dominant 9ths (open + movable voicings) ---
    Chord("E9", "9th", [
        _chord_pos("OPEN", 1, [0, 2, 0, 1, 0, 2], [0, 2, 0, 1, 0, 3]),
        _chord_pos("7TH FRET", 6, [MUTED, 7, 6, 7, 7, 7], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1, 7)),
    ]),
    Chord("A9", "9th", [
        _chord_pos("OPEN", 1, [MUTED, 0, 2, 4, 2, 3], [0, 0, 1, 4, 2, 3]),
    ]),
    Chord("B9", "9th", [
        _chord_pos("OPEN", 1, [MUTED, 2, 1, 2, 2, 2], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1, 2)),
    ]),
    Chord("C9", "9th", [
        _chord_pos("OPEN", 1, [MUTED, 3, 2, 3, 3, 3], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1, 3)),
    ]),
    Chord("Eb9", "9th", [
        _chord_pos("6TH FRET", 5, [MUTED, 6, 5, 6, 6, 6], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1, 6)),
    ]),
    Chord("D9", "9th", [
        _chord_pos("5TH FRET", 4, [MUTED, 5, 4, 5, 5, 5], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1, 5)),
    ]),
    Chord("F9", "9th", [
        _chord_pos("8TH FRET", 7, [MUTED, 8, 7, 8, 8, 8], [0, 2, 1, 3, 3, 3], barre=(3, 3, 1, 8)),
    ]),
    Chord("G9", "9th", [
        _chord_pos("3RD FRET", 3, [3, 5, 3, 4, 3, 5], [1, 3, 1, 2, 1, 4], barre=(1, 6, 2, 3)),
    ]),
]

# Give the open triads movable barre voicings up the neck (E-shape / A-shape), so each
# can be played in more than one place (e.g. D major open, A-shape at 5, E-shape at 10).
_CAGED_EXTRA = {
    "E MAJOR": [_a_major(7)],
    "A MAJOR": [_e_major(5)],
    "D MAJOR": [_a_major(5), _e_major(10)],
    "G MAJOR": [_e_major(3), _a_major(10)],
    "C MAJOR": [_a_major(3), _e_major(8)],
    "E MINOR": [_a_minor(7)],
    "A MINOR": [_e_minor(5)],
    "D MINOR": [_a_minor(5), _e_minor(10)],
}
for _chord in CHORDS:
    if _chord.name in _CAGED_EXTRA:
        _chord.positions.extend(_CAGED_EXTRA[_chord.name])


# --- scales ---------------------------------------------------------------

# Every scale type in all 12 keys, each generated at all neck positions.
_SCALE_TYPES = [
    ("min_pent", "MINOR PENTATONIC"),
    ("maj_pent", "MAJOR PENTATONIC"),
    ("major", "MAJOR SCALE"),
    ("mixolydian", "MIXOLYDIAN"),
]
_SCALE_ROOTS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]

SCALES: list[Scale] = [
    s for kind, disp in _SCALE_TYPES for root in _SCALE_ROOTS
    for s in [_gen_scale(f"{root} {disp}", root, kind)] if s.positions
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

"""Generate a small bundled Guitar Pro demo (assets/tabs/scale-demo.gp5).

Used as out-of-box content for the tempo-synced player and as a test fixture.
Run: PYTHONPATH=. ./venv/bin/python scripts/make_fixture_gp.py
"""

import os

import guitarpro as gp
from guitarpro import Beat, BeatStatus, Duration, Measure, MeasureHeader, Note, Song

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "tabs", "scale-demo.gp5")

# A minor pentatonic, eighth notes, climbing then descending — 4 bars of 4/4.
# Each entry is (string, fret); GP strings: 1 = high e ... 6 = low E.
PATTERN = [
    [(6, 5), (6, 8), (5, 5), (5, 7), (4, 5), (4, 7), (3, 5), (3, 7)],
    [(2, 5), (2, 8), (1, 5), (1, 8), (1, 8), (1, 5), (2, 8), (2, 5)],
    [(3, 7), (3, 5), (4, 7), (4, 5), (5, 7), (5, 5), (6, 8), (6, 5)],
    [(6, 5), (5, 5), (4, 5), (3, 5), (2, 5), (1, 5), (1, 8), (1, 5)],
]


def main() -> None:
    song = Song()
    song.title = "Scale Demo"
    song.artist = "Tabby"
    song.tempo = 100
    track = song.tracks[0]

    n = len(PATTERN)
    qt = Duration.quarterTime          # ticks per quarter note (960)
    measure_ticks = 4 * qt             # 4/4 bar
    while len(song.measureHeaders) < n:
        song.addMeasureHeader(MeasureHeader(number=len(song.measureHeaders) + 1))
    while len(track.measures) < n:
        header = song.measureHeaders[len(track.measures)]
        track.measures.append(Measure(track, header))

    # GP positions are absolute ticks; measure 1 starts at one quarter (qt).
    for i, header in enumerate(song.measureHeaders):
        header.start = qt + i * measure_ticks

    for i, (measure, bar) in enumerate(zip(track.measures, PATTERN)):
        voice = measure.voices[0]
        voice.beats.clear()
        pos = song.measureHeaders[i].start
        for string, fret in bar:
            beat = Beat(voice)
            beat.status = BeatStatus.normal    # else the reader treats it as a 0-length rest
            beat.duration = Duration(value=8)  # eighth note
            beat.start = pos
            note = Note(beat)
            note.string = string
            note.value = fret
            beat.notes.append(note)
            voice.beats.append(beat)
            pos += beat.duration.time

    gp.write(song, OUT)
    print(f"wrote {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()

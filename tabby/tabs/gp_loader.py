"""Load Guitar Pro files (.gp3/.gp4/.gp5) into the timed model via PyGuitarPro."""

from __future__ import annotations

import os

from .model import TimedBeat, TimedNote, TimedSong, TimedTrack

GP_EXTENSIONS = (".gp3", ".gp4", ".gp5")


def is_gp_file(path: str) -> bool:
    return path.lower().endswith(GP_EXTENSIONS)


def load(path: str) -> TimedSong:
    import guitarpro  # imported lazily so the text player works without the dep

    song = guitarpro.parse(path)
    tracks: list[TimedTrack] = []
    for t in song.tracks:
        tuning = [s.value for s in sorted(t.strings, key=lambda s: s.number)]
        beats: list[TimedBeat] = []
        pos = 0.0
        for measure in t.measures:
            # Voice 0 is the lead voice; second voices are ignored for now.
            for beat in measure.voices[0].beats:
                qn = beat.duration.time / beat.duration.quarterTime
                notes = [TimedNote(string=n.string, fret=n.value) for n in beat.notes]
                beats.append(TimedBeat(start=pos, duration=qn, notes=notes))
                pos += qn
        tracks.append(TimedTrack(name=t.name or f"TRACK {len(tracks) + 1}", tuning=tuning, beats=beats))

    title = song.title or os.path.splitext(os.path.basename(path))[0]
    return TimedSong(title=title, artist=song.artist or "", tempo=float(song.tempo or 120), tracks=tracks)

"""Headless smoke test: exercise screens, navigation, and pitch detection."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np

# Disable real audio devices so the test never prompts for mic access.
import tabby.audio.engine as eng
eng.sd = None

from tabby.audio import pitch
from tabby.audio.engine import SAMPLE_RATE
from tabby.app import App


def test_pitch():
    # A2 = 110 Hz with a couple harmonics, like a plucked string.
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    sig = (np.sin(2 * np.pi * 110 * t)
           + 0.5 * np.sin(2 * np.pi * 220 * t)
           + 0.25 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
    freq = pitch.detect_frequency(sig[:2048], SAMPLE_RATE)
    assert freq is not None, "no pitch detected"
    note = pitch.frequency_to_note(freq)
    assert note.label == "A2", f"expected A2, got {note.label} ({freq:.1f} Hz)"
    assert abs(note.cents) < 15, f"cents off: {note.cents}"
    # Silence should yield nothing.
    assert pitch.detect_frequency(np.zeros(2048, np.float32), SAMPLE_RATE) is None
    print(f"  pitch: {freq:.1f} Hz -> {note.label} ({note.cents:+.1f} cents) OK")


def test_screens():
    app = App(fullscreen=False, scale=2)
    for name in ["tuner", "metronome", "tabs", "assistant", "settings"]:
        app.navigate(name)
        for _ in range(3):
            app.current.update(0.05)
            app._draw()
        assert app.current.title
        app.go_back()
    # Back at home; render a few frames.
    for _ in range(3):
        app.current.update(0.05)
        app._draw()
    app._shutdown()
    print("  screens: navigated tuner/metronome/tabs/assistant/settings OK")


def test_tab_player():
    app = App(fullscreen=False, scale=2)
    app.navigate("tabs")
    screen = app.current
    assert screen.entries, "no tabs found (bundled samples missing?)"
    text_entries = [e for e in screen.entries if e.kind == "text"]
    gp_entries = [e for e in screen.entries if e.kind == "gp"]
    assert text_entries and gp_entries, "expected both text and GP sample tabs"

    # --- text player: manual scroll ---
    screen._open_local(text_entries[0])()
    assert screen.mode == "play" and screen.kind == "text" and screen.scroller is not None
    sc = screen.scroller
    sc.to_top(); sc.speed = 4.0; sc.playing = True
    for _ in range(20):           # 1.0s
        screen.update(0.05)
    expected = min(4.0, sc.max_offset)
    assert abs(sc.offset - expected) < 0.5, f"text scrolled {sc.offset:.2f}, expected ~{expected:.2f}"
    screen._to_browse()

    # --- synced GP player: tempo cursor + loop ---
    screen._open_local(gp_entries[0])()
    assert screen.mode == "play" and screen.kind == "synced" and screen.player is not None
    p = screen.player
    p.to_start(); p.playing = True
    for _ in range(20):           # 1.0s at tempo bpm
        screen.update(0.05)
    expected_beats = p.tempo / 60.0   # rate 1.0
    assert abs(p.pos - min(expected_beats, p.total)) < 0.3, f"synced pos {p.pos:.2f}, expected ~{expected_beats:.2f}"
    # A/B loop wraps the cursor.
    p.pos = 1.0; p.set_a(); p.pos = 2.0; p.set_b()
    assert p.loop_active
    p.pos = 1.99
    screen.update(0.2)            # crosses loop_b -> wraps back to loop_a
    assert p.pos < 2.0, f"loop did not wrap: pos={p.pos:.2f}"
    app._shutdown()
    print(f"  tab player: {len(text_entries)} text + {len(gp_entries)} GP tabs; "
          f"text scroll {expected:.1f} lines/1s, synced {expected_beats:.1f} beats/1s, A/B loop OK")


def test_songsterr_flow():
    import time
    from tabby.tabs import songsterr as ss
    from tabby.tabs.model import TimedBeat, TimedNote, TimedSong, TimedTrack

    # Mock the network so the test is offline + deterministic.
    ss.search = lambda q, size=24: [ss.SongResult(1, "Metallica", "One", True)]
    ss.tracks = lambda sid: [ss.TrackInfo(0, "Distortion Guitar", "Lead", False, False),
                             ss.TrackInfo(1, "Voice", "Vocals", True, False)]

    def fake_load(sid, idx):
        beats = [TimedBeat(start=float(i), duration=1.0, notes=[TimedNote(1, i % 6)]) for i in range(8)]
        return TimedSong("One", "Metallica", 120.0, [TimedTrack("Lead", [64, 59, 55, 50, 45, 40], beats)])
    ss.load_song = fake_load

    def wait(screen, timeout=3.0):
        t0 = time.time()
        while screen._loading and time.time() - t0 < timeout:
            screen.update(0.01)
            time.sleep(0.005)
        screen.update(0.01)

    app = App(fullscreen=False, scale=2)
    app.navigate("tabs")
    screen = app.current

    screen._to_search()
    assert screen.mode == "search" and screen.kb is not None
    screen.kb.text = "one"
    screen.kb._submit()             # -> async search
    wait(screen)
    assert screen.mode == "results" and screen.results, "search produced no results"

    screen._pick_song(screen.results[0])()   # -> async tracks
    wait(screen)
    assert screen.mode == "tracks" and screen.track_infos

    screen._pick_track(screen.track_infos[0])()   # -> async load_song
    wait(screen)
    assert screen.mode == "play" and screen.kind == "synced" and screen.player is not None
    p = screen.player
    p.playing = True
    for _ in range(20):
        screen.update(0.05)
    assert p.pos > 0, "synced Songsterr playback did not advance"
    app._shutdown()
    print("  songsterr flow: search -> results -> track -> synced play OK")


if __name__ == "__main__":
    test_pitch()
    test_screens()
    test_tab_player()
    test_songsterr_flow()
    print("SMOKE TEST PASSED")

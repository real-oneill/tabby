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
    # Open the first tab and enter play mode.
    screen._open(screen.entries[0].path)()
    assert screen.mode == "play" and screen.scroller is not None
    sc = screen.scroller
    sc.to_top()
    sc.speed = 4.0
    sc.playing = True
    for _ in range(20):           # 20 * 0.05s = 1.0s of playback
        screen.update(0.05)
    expected = min(4.0, sc.max_offset)
    assert abs(sc.offset - expected) < 0.5, f"scrolled {sc.offset:.2f}, expected ~{expected:.2f}"
    # Drag-to-scrub and jump-to-top.
    sc.drag_by(0, 30, 10)
    assert sc.offset != expected
    screen._to_top()
    assert sc.offset == 0.0
    app._shutdown()
    print(f"  tab player: loaded {len(screen.entries)} tabs, scrolled {expected:.1f} lines/1s OK")


if __name__ == "__main__":
    test_pitch()
    test_screens()
    test_tab_player()
    print("SMOKE TEST PASSED")

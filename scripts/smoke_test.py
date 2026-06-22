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


if __name__ == "__main__":
    test_pitch()
    test_screens()
    print("SMOKE TEST PASSED")

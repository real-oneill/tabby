"""Render representative screen states to PNGs for visual review (headless)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import tabby.audio.engine as eng
eng.sd = None  # no real audio devices

from tabby.app import App
from tabby.audio.pitch import NoteReading

OUT = os.path.join(os.path.dirname(__file__), "..", "preview")
os.makedirs(OUT, exist_ok=True)


def save(app, name):
    app._draw()
    big = pygame.transform.scale(app.canvas, (app.canvas.get_width() * 3, app.canvas.get_height() * 3))
    pygame.image.save(big, os.path.join(OUT, f"{name}.png"))
    print(f"  wrote preview/{name}.png")


def main():
    app = App(fullscreen=False, scale=2)

    save(app, "home")

    app.navigate("tuner")
    tuner = app.current
    tuner.no_audio = False
    tuner.reading = NoteReading(freq=80.6, name="E", octave=2, cents=-18.0)
    tuner.smooth_cents = -18.0
    tuner.since_sound = 0.0
    save(app, "tuner")
    app.go_back()

    app.navigate("metronome")
    metro = app.current
    metro.no_audio = False
    metro.metro.tempo = 120
    metro.metro.current_beat = 0
    metro.metro.running = True
    metro.update(0.0)
    save(app, "metronome")
    metro.metro.running = False
    app.go_back()

    app.navigate("settings")
    save(app, "settings")
    app.go_back()

    app.navigate("tabs")
    tabs = app.current
    save(app, "tabs_browse")
    # Open a tab and scroll partway in for the player view.
    tabs._open(tabs.entries[0].path)()
    tabs.scroller.speed = 3.0
    tabs.scroller.playing = True
    for _ in range(40):
        tabs.update(0.05)
    tabs.update(0.0)
    save(app, "tabs_play")
    app.go_back()

    app._shutdown()
    print("DONE")


if __name__ == "__main__":
    main()

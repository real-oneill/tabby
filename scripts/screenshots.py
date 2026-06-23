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
    # Text player: open a text tab and scroll partway in.
    text_entry = next(e for e in tabs.entries if e.kind == "text")
    tabs._open_local(text_entry)()
    tabs.scroller.speed = 3.0
    tabs.scroller.playing = True
    for _ in range(40):
        tabs.update(0.05)
    tabs.update(0.0)
    save(app, "tabs_text")
    tabs._to_browse()
    # Synced GP player: open the Guitar Pro demo, play in a bit, set an A/B loop.
    gp_entry = next(e for e in tabs.entries if e.kind == "gp")
    tabs._open_local(gp_entry)()
    tabs.player.playing = True
    for _ in range(70):
        tabs.update(0.05)
    tabs.player.pos = 2.5
    tabs.player.set_a()
    tabs.player.pos = 5.5
    tabs.player.set_b()
    tabs.player.pos = 3.2
    tabs.update(0.0)
    save(app, "tabs_synced")
    # Songsterr search keyboard.
    tabs._to_search()
    tabs.kb.text = "master of puppets"
    save(app, "tabs_search")
    # Songsterr results (mocked, no network).
    from tabby.tabs import songsterr as ss
    tabs._on_results([
        ss.SongResult(455118, "Metallica", "Master of Puppets", True),
        ss.SongResult(15366, "Primus", "Master of Puppets", True),
        ss.SongResult(393819, "Metallica", "Master of Puppets (Acoustic)", True),
    ])
    save(app, "tabs_results")
    app.go_back()

    app._shutdown()
    print("DONE")


if __name__ == "__main__":
    main()

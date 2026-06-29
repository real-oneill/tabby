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

    app.navigate("assistant")
    asst = app.current
    asst.state = "replying"
    asst.transcript = "give me a warmup tip"
    asst.reply = "Try a chromatic warmup: one finger per fret, slow and even."
    for _ in range(6):
        asst.cat.update(0.05)
    save(app, "assistant")
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
    # Delete mode + confirmation modal.
    tabs._to_browse()
    tabs.delete_mode = True
    tabs._build_browse()
    tabs.pending_delete = tabs.entries[0]
    save(app, "tabs_delete")
    app.go_back()

    app.navigate("chords")
    ch = app.current
    save(app, "chords_browse")
    # Chord diagram (E major, open) + the 12th-fret barre position.
    from tabby.chords import library
    emaj = next(c for c in library.CHORDS if c.name == "E MAJOR")
    ch._open_item(emaj)()
    save(app, "chords_chord_open")
    ch._cycle_pos(1)
    save(app, "chords_chord_12th")
    # Blues 9th chord.
    e9 = next(c for c in library.CHORDS if c.name == "E9")
    ch._open_item(e9)()
    save(app, "chords_chord_9th")
    # D major: previously the name overlapped the X/O markers (regression check).
    dmaj = next(c for c in library.CHORDS if c.name == "D MAJOR")
    ch._open_item(dmaj)()
    save(app, "chords_chord_dmajor")
    # A major 7 (new 7th-family chord).
    amaj7 = next(c for c in library.CHORDS if c.name == "A MAJOR 7")
    ch._open_item(amaj7)()
    save(app, "chords_chord_maj7")
    # Scale neck diagram (E minor pentatonic, open).
    ch._set_category("scale")()
    epent = next(s for s in library.SCALES if s.name == "E MINOR PENTATONIC")
    ch._open_item(epent)()
    save(app, "chords_scale")
    # A different pentatonic shape up the neck (A minor pentatonic, 7th-fret box).
    apent = next(s for s in library.SCALES if s.name == "A MINOR PENTATONIC")
    ch._open_item(apent)()
    ch._cycle_pos(2)
    save(app, "chords_scale_box")
    # Play-along view.
    ch._to_play()
    ch.player.playing = True
    for _ in range(24):
        ch.update(0.05)
    ch.update(0.0)
    save(app, "chords_play")
    app.go_back()

    app._shutdown()
    print("DONE")


if __name__ == "__main__":
    main()

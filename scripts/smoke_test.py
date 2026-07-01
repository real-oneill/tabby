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
    for name in ["tuner", "metronome", "tabs", "chords", "assistant", "settings"]:
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
    import os
    import tempfile
    import time
    from tabby.tabs import songsterr as ss
    from tabby.tabs.library import TabLibrary
    from tabby.tabs.model import TimedBeat, TimedNote, TimedSong, TimedTrack

    # Mock the network so the test is offline + deterministic.
    ss.search = lambda q, size=24: [ss.SongResult(1, "Metallica", "One", True)]

    def fake_full(sid):
        def track(name, base):
            beats = [TimedBeat(float(i), 1.0, [TimedNote(1, (i + base) % 6)]) for i in range(8)]
            return TimedTrack(name, [64, 59, 55, 50, 45, 40], beats)
        return TimedSong("One", "Metallica", 120.0, [track("Lead", 0), track("Bass", 2)], default_track=1)
    ss.load_full_song = fake_full

    def wait(screen, timeout=3.0):
        t0 = time.time()
        while screen._loading and time.time() - t0 < timeout:
            screen.update(0.01)
            time.sleep(0.005)
        screen.update(0.01)

    tmp = tempfile.mkdtemp()
    app = App(fullscreen=False, scale=2)
    app.config._data["tabs_dir"] = tmp        # save retrieved tabs here, not the real folder
    app.navigate("tabs")
    screen = app.current

    screen._to_search()
    assert screen.mode == "search" and screen.kb is not None
    screen.kb.text = "one"
    screen.kb._submit()             # -> async search
    wait(screen)
    assert screen.mode == "results" and screen.results, "search produced no results"

    screen._pick_song(screen.results[0])()   # -> async load_full_song (+ auto-save)
    wait(screen)
    assert screen.mode == "play" and screen.kind == "synced" and screen.player is not None
    p = screen.player
    assert len(p.song.tracks) == 2, "expected multi-track load"
    assert p.track_index == 1, "should open on default_track"
    p.cycle_track()
    assert p.track_index == 0, "TRK should cycle tracks"
    p.playing = True
    for _ in range(20):
        screen.update(0.05)
    assert p.pos > 0, "synced Songsterr playback did not advance"

    # Auto-saved .tabby is reloadable and preserves multi-track + default.
    saved = TabLibrary(tmp).entries()
    tabby = [e for e in saved if e.kind == "tabby"]
    assert tabby, "retrieved tab was not saved to the tabs folder"
    reloaded = TabLibrary.load_tabby(tabby[0].path)
    assert len(reloaded.tracks) == 2 and reloaded.default_track == 1, "saved tab lost data"

    # Delete-from-list: the saved tab is deletable; bundled samples are not.
    screen._to_browse()
    screen.on_enter()               # rescan entries from the (tmp) tabs dir + bundled
    saved_entry = next(e for e in screen.entries if e.kind == "tabby")
    bundled = next(e for e in screen.entries if not e.deletable)
    assert saved_entry.deletable and not bundled.deletable
    screen.delete_mode = True
    screen._ask_delete(saved_entry)()
    assert screen.pending_delete is saved_entry
    screen._do_delete()
    assert not os.path.exists(saved_entry.path), "tab file was not deleted"
    assert all(e.path != saved_entry.path for e in screen.entries), "deleted tab still listed"
    app._shutdown()
    print("  songsterr flow: search -> full load -> multi-track play + auto-save/reload + delete OK")


def test_chords_scales():
    from tabby.chords import library
    from tabby.chords.songbuild import chord_song, scale_song

    app = App(fullscreen=False, scale=2)
    app.navigate("chords")
    screen = app.current
    assert screen.mode == "browse" and screen.section is None, "should open on the top menu"

    # CHORDS section: every chord group resolves to items.
    from tabby.screens.chordsscales import _CHORD_GROUPS, _SCALE_GROUPS, _chord_group
    for c in library.CHORDS:
        assert _chord_group(c) in {"MAJOR", "MINOR", "POWER", "7TH", "9TH"}, c.name
    screen._open_section("CHORDS")()
    for _label, key in _CHORD_GROUPS:
        screen._open_group(key)()
        assert screen._group_items(), f"chord group {key} is empty"

    # SCALES section: every type is offered in all 12 keys. Drill to A major pentatonic.
    screen._open_section("SCALES")()
    for _label, key in _SCALE_GROUPS:
        screen._open_group(key)()
        assert len(screen._group_items()) == 12, f"scale type {key} != 12 keys"
    screen._open_group("maj_pent")()
    scale = next(s for s in screen._group_items() if s.name == "A MAJOR PENTATONIC")
    screen._open_item(scale)()
    assert screen.mode == "detail" and screen.kind == "scale"
    screen.draw(app.canvas)                 # neck diagram must not crash
    screen._to_play()
    assert screen.player is not None and screen.player.track.total_beats > 0
    p = screen.player
    p.playing = True
    for _ in range(20):                     # 1.0s
        screen.update(0.05)
    expected_beats = p.tempo / 60.0
    assert abs(p.pos - min(expected_beats, p.total)) < 0.3, f"scale pos {p.pos:.2f}"

    # Chord: multiple neck positions (E major open + 12th) + strum/arp toggle.
    emaj = next(c for c in library.CHORDS if c.name == "E MAJOR")
    screen._open_item(emaj)()
    assert len(emaj.positions) > 1, "E major should have 2 positions"
    screen.draw(app.canvas)                 # chord box must not crash
    screen._cycle_pos(1)
    assert screen.pos_index == 1
    screen._toggle_chord_mode()
    assert screen.chord_mode == "strum"
    screen._to_play()
    assert screen.player is not None

    # Builders: open strings sound, muted are skipped; beat counts as specified.
    pos = emaj.positions[0]
    non_muted = [h for h in pos.hits if h.fret != library.MUTED]
    strum = chord_song(emaj, pos, mode="strum", repeats=4)
    assert len(strum.tracks[0].beats) == 5                       # 4 strums + trailing rest
    assert len(strum.tracks[0].beats[0].notes) == len(non_muted)
    arp = chord_song(emaj, pos, mode="arpeggio")
    assert len(arp.tracks[0].beats) == len(non_muted) + 1
    ss = scale_song(scale, scale.positions[0], descend=True)
    assert len(ss.tracks[0].beats) == 2 * len(scale.positions[0].sequence) + 1

    # Every chord/scale position is structurally sane and renders without crashing.
    for chord in library.CHORDS:
        for cp in chord.positions:
            assert len(cp.hits) == 6, f"{chord.name} position needs 6 strings"
            assert all(h.fret == library.MUTED or h.fret >= 0 for h in cp.hits), chord.name
            assert all(0 <= h.finger <= 4 for h in cp.hits), f"{chord.name} bad finger"
            screen._open_item(chord)()
            screen.draw(app.canvas)
    for sc in library.SCALES:
        for spos in sc.positions:
            assert spos.sequence, f"{sc.name} position has no play-along sequence"
            assert spos.roots, f"{sc.name} position has no root marked"
            screen._open_item(sc)()
            screen.draw(app.canvas)

    # Assistant voice lookup lands on the right diagram.
    from tabby.assistant import dispatch
    while len(app.stack) > 1:
        app.go_back()
    dispatch.run_actions(app, [{"type": "show_chord", "name": "E major"}])
    assert app.current.title == "CHORDS" and app.current.selected.name == "E MAJOR", "voice lookup failed"
    app._shutdown()
    print("  chords/scales: browse->detail->play, diagrams, builders, voice lookup OK")


def test_assistant():
    import time
    app = App(fullscreen=False, scale=2)

    # Action dispatch maps onto the app.
    from tabby.assistant import dispatch
    dispatch.run_actions(app, [{"type": "set_tempo", "bpm": 95}])
    assert int(app.config.get("tempo")) == 95, "set_tempo action did not apply"
    dispatch.run_actions(app, [{"type": "navigate", "screen": "tuner"}])
    assert app.current.title == "TUNER", "navigate action did not switch screens"
    while len(app.stack) > 1:
        app.go_back()

    # Voice -> agent -> reply + action, with both mocked (offline).
    app.navigate("assistant")
    s = app.current
    s.client.cfg = {"host": "x", "client_id": "x", "client_secret": "x", "endpoint": "x", "mode": "fm"}
    s.client.ask = lambda text, context=None: {"reply": "Loading it now!", "actions": [{"type": "set_tempo", "bpm": 140}]}
    assert s.client.configured

    # Simulate a finished transcript -> agent -> reply + action.
    s._on_transcript("set tempo to 140")
    for _ in range(60):
        s.update(0.02)
        if s.state == "replying":
            break
        time.sleep(0.005)
    assert s.state == "replying", f"assistant stuck in {s.state}"
    assert s.reply == "Loading it now!"
    assert int(app.config.get("tempo")) == 140, "agent action did not run"

    # identify flow: agent emits 'identify' -> screen recognizes + shows now-playing.
    import tabby.assistant.songid as songid_mod

    class _FakeSID:
        available = True

        def __init__(self, input_device=None):
            pass

        def identify(self, seconds=6.0):
            return {"title": "Wonderwall", "artist": "Oasis", "art_url": ""}

    songid_mod.SongID = _FakeSID
    s.client.ask = lambda text, context=None: {"reply": "Let me listen", "actions": [{"type": "identify"}]}
    s._on_transcript("what's playing")
    for _ in range(60):
        s.update(0.02)
        if s.state in ("now_playing", "replying"):
            break
        time.sleep(0.005)
    assert s.state == "now_playing" and s.now_playing["title"] == "Wonderwall", f"identify failed: {s.state}"
    s.draw(app.canvas)   # now-playing render must not crash
    app._shutdown()
    print("  assistant: agent->action, identify->now-playing OK")


if __name__ == "__main__":
    test_pitch()
    test_screens()
    test_tab_player()
    test_songsterr_flow()
    test_chords_scales()
    test_assistant()
    print("SMOKE TEST PASSED")

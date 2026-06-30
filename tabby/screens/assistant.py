"""ASSIST screen: an animated 8-bit cat, push-to-talk voice, and the agent flow.

Voice (whisper.cpp) -> Databricks agent -> {reply, actions} -> run actions + show reply.
No keyboard: all AI features live here.
"""

from __future__ import annotations

import io
import os
import threading
import time
import urllib.request

import pygame

from .. import theme
from ..app import Screen, TOPBAR_H
from ..assistant import dispatch
from ..assistant.cat import Cat
from ..assistant.client import AgentClient
from ..assistant.stt import VoiceInput
from ..audio.sfx import load_wav
from ..ui.widgets import Button, draw_panel, draw_text

_REPLY_HOLD = 5.0   # seconds to keep showing a reply before returning to idle
_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")


def _wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            if line:
                out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out[:4]


class AssistantScreen(Screen):
    title = "ASSIST"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.cat = Cat()
        self.client = AgentClient()
        self.voice = VoiceInput(input_device=app.config.get("input_device"))
        self.state = "idle"            # idle|listening|thinking|replying|error
        self.transcript = ""
        self.reply = ""
        self.status = ""
        self._reply_t = 0.0
        self._busy = False
        self._async = None             # ("ok", value) | ("err", msg)
        self._after = None
        self._press_t = None           # when the talk button went down
        self._tap_mode = False         # tapped (vs held): auto-stop on silence
        self.now_playing = None        # {title, artist, art} after a song-ID

        self.talk_btn = Button((100, 208, 200, 28), "HOLD OR TAP TO TALK", self._noop,
                               color=theme.PURPLE, text_color=theme.WHITE, font_size=10)
        self.reply_box = (12, 150, theme.INTERNAL_W - 24, 52)

        # A cat meow that plays through the speaker when the assistant answers.
        self.no_audio = True
        try:
            self._meow = load_wav(os.path.join(_ASSETS, "sounds", "cat.wav"), peak=0.7)
        except Exception:  # noqa: BLE001 - missing/bad asset shouldn't break the screen
            self._meow = None

    def on_enter(self) -> None:
        # Open the output stream for the meow; warm up whisper for an instant first tap.
        self.no_audio = not self.app.audio.start_output()
        threading.Thread(target=self._prewarm, daemon=True).start()

    def _prewarm(self) -> None:
        try:
            self.voice._ensure_model()
        except Exception:  # noqa: BLE001
            pass

    def on_exit(self) -> None:
        if self.voice.recording:
            self.voice.stop_recording()
        self.app.audio.stop_output()

    @staticmethod
    def _noop() -> None:
        pass

    def _play_meow(self) -> None:
        """Play the cat sound through the speaker (no-op if audio out is unavailable)."""
        if self._meow is not None and not self.no_audio:
            self.app.audio.play_sample(self._meow)

    # --- async helper -----------------------------------------------------

    def _run_async(self, fn, on_done) -> None:
        self._busy = True
        self._async = None
        self._after = on_done

        def worker():
            try:
                self._async = ("ok", fn())
            except Exception as exc:  # noqa: BLE001
                self._async = ("err", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _pump(self) -> None:
        if not self._busy or self._async is None:
            return
        status, payload = self._async
        cb = self._after
        self._busy = False
        self._async = None
        self._after = None
        if status == "ok":
            cb(payload)
        else:
            self._fail(payload)

    def _fail(self, msg: str) -> None:
        self.state = "error"
        self.status = _short(msg)

    # --- voice flow -------------------------------------------------------

    _HOLD = 0.45        # press longer than this = hold-to-talk
    _SILENCE = 2.0      # tap-to-talk auto-stops after this much trailing silence
    _MAX_REC = 15.0     # hard cap on a single utterance

    def _begin_listen(self) -> None:
        if self._busy or self.state in ("listening", "thinking") or self.voice.recording:
            return
        if not self.client.configured:
            self.state = "error"
            self.status = "ASSISTANT NOT SET UP (SEE CONFIG)"
            return
        if not self.voice.has_audio:
            self.state = "error"
            self.status = "NO MICROPHONE"
            return
        try:
            self.voice.start_recording()
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
            return
        self.transcript = ""
        self.reply = ""
        self._press_t = time.monotonic()
        self._tap_mode = False
        self.state = "listening"
        self.status = "LISTENING..."

    def _end_listen(self) -> None:
        audio = self.voice.stop_recording()
        if len(audio) < 16000 * 0.3:        # < 0.3s -> ignore stray tap
            self.state = "idle"
            self.status = ""
            return
        self.state = "thinking"
        self.status = "THINKING..."
        self._run_async(lambda: self.voice.transcribe(audio), self._on_transcript)

    def _on_transcript(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            self.state = "idle"
            self.status = ""
            return
        self.transcript = text
        self.state = "thinking"
        self.status = "THINKING..."
        context = {"screen": self.app.current.title}
        self._run_async(lambda: self.client.ask(text, context), self._on_reply)

    def _on_reply(self, result: dict) -> None:
        self.reply = result.get("reply", "")
        self.status = ""
        self._reply_t = 0.0
        actions = [a for a in (result.get("actions") or []) if isinstance(a, dict)]
        wants_identify = any(a.get("type") == "identify" for a in actions)
        dispatch.run_actions(self.app, [a for a in actions if a.get("type") != "identify"])
        if wants_identify:
            self._start_identify()
        else:
            self.state = "replying"
            self._play_meow()

    # --- song identification ----------------------------------------------

    def _start_identify(self) -> None:
        self.now_playing = None
        self.state = "identifying"
        self.status = "LISTENING FOR MUSIC..."
        self._run_async(self._identify_work, self._on_identified)

    def _identify_work(self):
        from ..assistant.songid import SongID
        sid = SongID(input_device=self.app.config.get("input_device"))
        if not sid.available:
            raise RuntimeError("song id not set up")
        rec = sid.identify(6.0)
        if not rec or not (rec.get("title") or rec.get("artist")):
            return None
        rec["art"] = self._fetch_art(rec.get("art_url"))
        return rec

    @staticmethod
    def _fetch_art(url):
        if not url:
            return None
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = r.read()
            img = pygame.image.load(io.BytesIO(data))
            return pygame.transform.smoothscale(img, (84, 84))
        except Exception:  # noqa: BLE001
            return None

    def _on_identified(self, rec) -> None:
        self._reply_t = 0.0
        self.status = ""               # clear "LISTENING FOR MUSIC..."
        if not rec:
            self.reply = "Hmm, I couldn't make out what's playing."
            self.state = "replying"
            self._play_meow()
            return
        self.now_playing = rec
        self.reply = f"That's {rec['title']} by {rec['artist']}"
        self.state = "now_playing"
        self._play_meow()

    # --- loop -------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._pump()
        # Auto-stop a tapped recording after trailing silence (or the hard cap).
        if self.state == "listening" and self.voice.recording:
            if self._tap_mode and (self.voice.silence_elapsed() >= self._SILENCE
                                   or self.voice.record_elapsed() >= self._MAX_REC):
                self._end_listen()
            elif not self._tap_mode and self.voice.record_elapsed() >= self._MAX_REC:
                self._end_listen()
        cat_state = {"identifying": "listening", "now_playing": "replying"}.get(self.state, self.state)
        self.cat.set_state(cat_state if cat_state in ("idle", "listening", "thinking", "replying") else "idle")
        self.cat.update(dt)
        self.talk_btn.text = {
            "listening": "LISTENING...", "thinking": "THINKING...", "identifying": "LISTENING...",
        }.get(self.state, "HOLD OR TAP TO TALK")
        if self.state in ("replying", "now_playing"):
            self._reply_t += dt
            if self._reply_t > _REPLY_HOLD:
                self.state = "idle"
                self.now_playing = None
                self.status = ""
                self.reply = ""

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        rect = self.talk_btn.rect
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and rect.collidepoint(pos):
            self._begin_listen()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.state == "listening" and self.voice.recording:
            held = self._press_t is not None and (time.monotonic() - self._press_t) >= self._HOLD
            if held:
                self._end_listen()       # hold-to-talk: release ends it
            else:
                self._tap_mode = True    # tap-to-talk: keep recording until silence

    # --- draw -------------------------------------------------------------

    def draw(self, surface) -> None:
        cx = theme.INTERNAL_W // 2
        if self.state == "now_playing" and self.now_playing:
            self._draw_now_playing(surface)
        else:
            self.cat.draw(surface, (cx, TOPBAR_H + 56))

        if self.transcript and self.state in ("thinking", "replying", "identifying", "now_playing"):
            draw_text(surface, _short('"' + self.transcript + '"', 46), 8, theme.TEXT_DIM,
                      center=(cx, 138))

        if self.reply and self.state in ("replying", "now_playing"):
            draw_panel(surface, self.reply_box, fill=theme.DARK, border=theme.PANEL_BORDER, width=1)
            for i, line in enumerate(_wrap(self.reply, 44)):
                draw_text(surface, line, 8, theme.TEXT, midleft=(self.reply_box[0] + 6, self.reply_box[1] + 12 + i * 12))
        elif self.status:
            color = theme.BAD if self.state == "error" else theme.TEXT_DIM
            draw_text(surface, self.status, 8, color, center=(theme.INTERNAL_W // 2, 168))
        elif self.state == "idle":
            draw_text(surface, "ASK ME TO TUNE, LOAD A SONG, OR WHAT'S PLAYING", 8, theme.TEXT_DIM,
                      center=(theme.INTERNAL_W // 2, 168))

        self.talk_btn.draw(surface)

    def _draw_now_playing(self, surface) -> None:
        cx = theme.INTERNAL_W // 2
        draw_text(surface, "NOW PLAYING", 8, theme.ACCENT_ALT, center=(cx, TOPBAR_H + 8))
        box = pygame.Rect(cx - 44, TOPBAR_H + 16, 88, 88)
        draw_panel(surface, box, fill=theme.DARK, border=theme.PANEL_BORDER, width=2)
        art = self.now_playing.get("art")
        if art is not None:
            surface.blit(art, (box.x + 2, box.y + 2))
        else:
            draw_text(surface, "?", 24, theme.TEXT_DIM, center=box.center)


def _short(text: str, n: int = 40) -> str:
    return text if len(text) <= n else text[: n - 1] + "~"

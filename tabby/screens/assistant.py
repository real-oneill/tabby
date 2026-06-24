"""ASSIST screen: an animated 8-bit cat, push-to-talk voice, and the agent flow.

Voice (whisper.cpp) -> Databricks agent -> {reply, actions} -> run actions + show reply.
No keyboard: all AI features live here.
"""

from __future__ import annotations

import threading
import time

import pygame

from .. import theme
from ..app import Screen, TOPBAR_H
from ..assistant import dispatch
from ..assistant.cat import Cat
from ..assistant.client import AgentClient
from ..assistant.stt import VoiceInput
from ..ui.widgets import Button, draw_panel, draw_text

_REPLY_HOLD = 5.0   # seconds to keep showing a reply before returning to idle


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

        self.talk_btn = Button((100, 208, 200, 28), "HOLD OR TAP TO TALK", self._noop,
                               color=theme.PURPLE, text_color=theme.WHITE, font_size=10)
        self.reply_box = (12, 150, theme.INTERNAL_W - 24, 52)

    def on_enter(self) -> None:
        # Warm up the whisper model in the background so the first tap is instant.
        threading.Thread(target=self._prewarm, daemon=True).start()

    def _prewarm(self) -> None:
        try:
            self.voice._ensure_model()
        except Exception:  # noqa: BLE001
            pass

    def on_exit(self) -> None:
        if self.voice.recording:
            self.voice.stop_recording()

    @staticmethod
    def _noop() -> None:
        pass

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
        self.state = "replying"
        self.status = ""
        self._reply_t = 0.0
        dispatch.run_actions(self.app, result.get("actions"))

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
        self.cat.set_state(self.state if self.state in ("idle", "listening", "thinking", "replying") else "idle")
        self.cat.update(dt)
        self.talk_btn.text = {
            "idle": "HOLD OR TAP TO TALK", "listening": "LISTENING...",
            "thinking": "THINKING...", "replying": "HOLD OR TAP TO TALK", "error": "HOLD OR TAP TO TALK",
        }.get(self.state, "HOLD OR TAP TO TALK")
        if self.state == "replying":
            self._reply_t += dt
            if self._reply_t > _REPLY_HOLD:
                self.state = "idle"

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
        self.cat.draw(surface, (theme.INTERNAL_W // 2, TOPBAR_H + 56))

        if self.transcript and self.state in ("thinking", "replying"):
            draw_text(surface, _short('"' + self.transcript + '"', 46), 8, theme.TEXT_DIM,
                      center=(theme.INTERNAL_W // 2, 138))

        if self.reply and self.state == "replying":
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


def _short(text: str, n: int = 40) -> str:
    return text if len(text) <= n else text[: n - 1] + "~"

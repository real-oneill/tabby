"""ASSIST screen: an animated 8-bit cat, push-to-talk voice, and the agent flow.

Voice (whisper.cpp) -> Databricks agent -> {reply, actions} -> run actions + show reply.
No keyboard: all AI features live here.
"""

from __future__ import annotations

import threading

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

        self.talk_btn = Button((100, 208, 200, 28), "TAP TO TALK", self._on_talk,
                               color=theme.PURPLE, text_color=theme.WHITE, font_size=12)
        self.reply_box = (12, 150, theme.INTERNAL_W - 24, 52)

    def on_exit(self) -> None:
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

    def _on_talk(self) -> None:
        if self._busy or self.state in ("listening", "thinking"):
            return
        if not self.client.configured:
            self.state = "error"
            self.status = "ASSISTANT NOT SET UP (SEE CONFIG)"
            return
        if not self.voice.ready:
            self.state = "error"
            self.status = "VOICE NOT SET UP (INSTALL WHISPER)"
            return
        self.transcript = ""
        self.reply = ""
        self.state = "listening"
        self.status = "LISTENING..."
        self._run_async(lambda: self.voice.listen(4.0), self._on_transcript)

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
        self.cat.set_state(self.state if self.state in ("idle", "listening", "thinking", "replying") else "idle")
        self.cat.update(dt)
        self.talk_btn.text = {
            "idle": "TAP TO TALK", "listening": "LISTENING...",
            "thinking": "THINKING...", "replying": "TAP TO TALK", "error": "TAP TO TALK",
        }.get(self.state, "TAP TO TALK")
        if self.state == "replying":
            self._reply_t += dt
            if self._reply_t > _REPLY_HOLD:
                self.state = "idle"

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        self.talk_btn.handle_event(event, pos)

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
            draw_text(surface, "ASK ME TO TUNE, SET TEMPO, OR LOAD A SONG", 8, theme.TEXT_DIM,
                      center=(theme.INTERNAL_W // 2, 168))

        self.talk_btn.draw(surface)


def _short(text: str, n: int = 40) -> str:
    return text if len(text) <= n else text[: n - 1] + "~"

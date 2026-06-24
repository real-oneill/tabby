"""An animated 8-bit cat playing a guitar, drawn procedurally on the canvas."""

from __future__ import annotations

import math

import pygame

from .. import theme

# Local palette (theme has no tan/string colors).
_BODY = theme.ORANGE
_BODY_DK = theme.BROWN
_INNER = theme.MAGENTA          # ear / nose
_MUZZLE = theme.WHITE
_EYE = theme.BLACK
_GTR = theme.BROWN
_GTR_DK = (92, 56, 24)
_NECK = (180, 140, 90)
_STRING = (210, 210, 210)
_HOLE = theme.BLACK
_NOTE = theme.ACCENT_ALT

# Animation cadence per state: (strum beats/sec, note spawn rate/sec).
_STATE_TEMPO = {
    "idle": (1.6, 0.0),
    "listening": (0.0, 0.0),
    "thinking": (0.0, 0.0),
    "replying": (4.0, 4.0),
}


class Cat:
    def __init__(self) -> None:
        self.t = 0.0
        self.state = "idle"
        self.blink = 0.0
        self._notes: list[list[float]] = []   # [x, y, age, drift]
        self._note_acc = 0.0

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            if state != "replying":
                self._notes.clear()

    def update(self, dt: float) -> None:
        self.t += dt
        self.blink = (self.blink + dt) % 4.0
        rate = _STATE_TEMPO.get(self.state, (1.6, 0.0))[1]
        if rate:
            self._note_acc += dt * rate
            while self._note_acc >= 1.0:
                self._note_acc -= 1.0
                self._notes.append([0.0, 0.0, 0.0, (-1.0 if len(self._notes) % 2 else 1.0)])
        for n in self._notes:
            n[2] += dt
        self._notes = [n for n in self._notes if n[2] < 1.4]

    # --- drawing ----------------------------------------------------------

    def draw(self, surface, center) -> None:
        cx, cy = center
        strum = _STATE_TEMPO.get(self.state, (1.6, 0.0))[0]
        phase = math.sin(self.t * strum * 2 * math.pi) if strum else 0.0

        self._body(surface, cx, cy)
        self._head(surface, cx, cy)
        self._guitar(surface, cx, cy)
        self._paws(surface, cx, cy, phase)
        if self.state == "thinking":
            self._thought(surface, cx, cy)
        self._draw_notes(surface, cx, cy)

    def _body(self, surface, cx, cy) -> None:
        # Sitting haunch.
        pygame.draw.ellipse(surface, _BODY, (cx - 26, cy + 2, 52, 46))
        pygame.draw.ellipse(surface, _BODY_DK, (cx - 26, cy + 2, 52, 46), 1)
        pygame.draw.ellipse(surface, _MUZZLE, (cx - 12, cy + 16, 24, 28))
        # Tail curling out to the left.
        pygame.draw.arc(surface, _BODY, (cx - 48, cy + 14, 34, 34), 0.4, 2.6, 5)

    def _head(self, surface, cx, cy) -> None:
        hy = cy - 18
        # Ears.
        for sx in (-1, 1):
            base = cx + sx * 16
            pygame.draw.polygon(surface, _BODY, [(base - 8, hy - 12), (base + 8, hy - 12), (base + sx * 2, hy - 26)])
            pygame.draw.polygon(surface, _INNER, [(base - 3, hy - 14), (base + 3, hy - 14), (base + sx * 1, hy - 22)])
        # Head.
        pygame.draw.circle(surface, _BODY, (cx, hy), 22)
        pygame.draw.circle(surface, _BODY_DK, (cx, hy), 22, 1)
        # Muzzle.
        pygame.draw.ellipse(surface, _MUZZLE, (cx - 13, hy + 2, 26, 16))
        # Eyes (blink: a short closed window each cycle).
        closed = self.blink > 3.8
        for sx in (-1, 1):
            ex = cx + sx * 9
            if closed:
                pygame.draw.line(surface, _EYE, (ex - 3, hy - 3), (ex + 3, hy - 3), 2)
            else:
                pygame.draw.circle(surface, _EYE, (ex, hy - 3), 3)
                pygame.draw.circle(surface, _MUZZLE, (ex + 1, hy - 4), 1)
        # Nose + mouth.
        pygame.draw.polygon(surface, _INNER, [(cx - 3, hy + 6), (cx + 3, hy + 6), (cx, hy + 9)])
        pygame.draw.line(surface, _BODY_DK, (cx, hy + 9), (cx, hy + 12), 1)
        pygame.draw.arc(surface, _BODY_DK, (cx - 7, hy + 8, 7, 7), 3.6, 6.0, 1)
        pygame.draw.arc(surface, _BODY_DK, (cx, hy + 8, 7, 7), 3.4, 5.8, 1)
        # Whiskers.
        for dy in (8, 12):
            pygame.draw.line(surface, _MUZZLE, (cx - 8, hy + dy), (cx - 22, hy + dy - 2), 1)
            pygame.draw.line(surface, _MUZZLE, (cx + 8, hy + dy), (cx + 22, hy + dy - 2), 1)

    def _guitar(self, surface, cx, cy) -> None:
        # Acoustic held across the lap: body lower-right, neck up to the upper-left.
        self._neck_end = (cx - 34, cy - 18)
        self._body_pt = (cx + 14, cy + 24)
        nx, ny = self._neck_end
        bx, by = self._body_pt
        # Neck (drawn first, body sits over its lower end).
        pygame.draw.line(surface, _NECK, (bx - 4, by - 6), (nx, ny), 7)
        pygame.draw.line(surface, _GTR_DK, (nx, ny), (nx - 6, ny - 4), 8)   # headstock
        # Figure-8 body: lower bout + smaller upper bout.
        pygame.draw.ellipse(surface, _GTR, (bx - 17, by - 6, 34, 30))
        pygame.draw.ellipse(surface, _GTR, (bx - 13, by - 20, 26, 24))
        pygame.draw.ellipse(surface, _GTR_DK, (bx - 17, by - 6, 34, 30), 1)
        pygame.draw.circle(surface, _HOLE, (bx, by + 4), 5)
        pygame.draw.line(surface, _GTR_DK, (bx - 7, by + 14), (bx + 7, by + 14), 2)  # bridge
        # Frets across the neck.
        for f in range(1, 5):
            fx = int(nx + (bx - 6 - nx) * f / 5)
            fy = int(ny + (by - 6 - ny) * f / 5)
            pygame.draw.line(surface, _GTR_DK, (fx - 2, fy - 2), (fx + 2, fy + 2), 1)
        # Strings down the neck to the bridge.
        for off in (-2, 0, 2):
            pygame.draw.line(surface, _STRING, (nx, ny + off), (bx + off, by + 14), 1)

    def _paws(self, surface, cx, cy, phase) -> None:
        bx, by = self._body_pt
        nx, ny = self._neck_end
        # Strumming paw over the soundhole, bobbing with the strum phase.
        sy = by + 3 + int(phase * 6)
        pygame.draw.circle(surface, _BODY, (bx + 9, sy), 5)
        pygame.draw.circle(surface, _BODY_DK, (bx + 9, sy), 5, 1)
        # Fretting paw on the neck near the headstock.
        pygame.draw.circle(surface, _BODY, (nx + 10, ny + 4), 5)
        pygame.draw.circle(surface, _BODY_DK, (nx + 10, ny + 4), 5, 1)

    def _thought(self, surface, cx, cy) -> None:
        n = int(self.t * 2) % 4
        for i in range(3):
            on = i < n
            col = _MUZZLE if on else theme.SHADOW
            pygame.draw.circle(surface, col, (cx + 26 + i * 7, cy - 40), 2)

    def _draw_notes(self, surface, cx, cy) -> None:
        bx, by = cx + 24, cy + 18      # rise up from the guitar, off to the side
        for x, y, age, drift in self._notes:
            ny = by - int(age * 34)
            nx = bx + int(drift * age * 14)
            alpha = 1.0 - age / 1.4
            col = _NOTE if alpha > 0.4 else theme.SHADOW
            pygame.draw.circle(surface, col, (nx, ny), 2)
            pygame.draw.line(surface, col, (nx + 2, ny), (nx + 2, ny - 6), 1)
            pygame.draw.line(surface, col, (nx + 2, ny - 6), (nx + 5, ny - 5), 1)

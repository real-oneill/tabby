"""An 8/16-bit pixel-sprite cat playing a guitar.

Everything is drawn as solid blocks snapped to a coarse pixel grid (CELL per sprite
pixel), so it reads as a chunky retro sprite rather than smooth vector art. Two strum
frames are animated by moving the picking paw.
"""

from __future__ import annotations

import pygame

from .. import theme

CELL = 4                      # internal pixels per sprite-pixel (chunky)
_GW, _GH = 24, 22             # sprite grid size in cells

# Palette.
_O = theme.ORANGE
_D = theme.BROWN              # outline / shading
_W = theme.WHITE
_K = theme.BLACK
_P = theme.MAGENTA           # nose / inner ear
_G = (150, 96, 40)           # guitar wood
_N = (198, 158, 108)         # neck
_S = (220, 220, 220)         # strings
_A = theme.ACCENT_ALT        # music notes

# Static blocks: (col, row, w, h, color). Drawn back-to-front.
_SPRITE = [
    # ears
    (5, 1, 3, 2, _O), (6, 0, 1, 1, _O), (6, 1, 1, 1, _P),
    (16, 1, 3, 2, _O), (17, 0, 1, 1, _O), (17, 1, 1, 1, _P),
    # head
    (7, 2, 10, 1, _O), (6, 3, 12, 1, _O), (5, 4, 14, 5, _O),
    (6, 9, 12, 1, _O), (7, 10, 10, 1, _O),
    # eyes + shine
    (8, 5, 2, 2, _K), (14, 5, 2, 2, _K), (9, 5, 1, 1, _W), (15, 5, 1, 1, _W),
    # muzzle + nose
    (9, 7, 6, 3, _W), (11, 7, 2, 1, _P),
    # body
    (6, 11, 12, 1, _O), (5, 12, 14, 8, _O), (6, 20, 12, 1, _O),
    (8, 14, 5, 5, _W),                                   # belly
    # tail
    (3, 16, 2, 2, _O), (2, 17, 1, 2, _O),
    # guitar neck (stepped up-left) + headstock
    (12, 15, 2, 1, _N), (11, 14, 2, 1, _N), (10, 13, 2, 1, _N), (9, 12, 2, 1, _N),
    (8, 11, 2, 1, _N), (7, 10, 2, 1, _N), (6, 9, 2, 1, _N), (5, 8, 2, 1, _N),
    (4, 7, 2, 2, _D),
    (9, 12, 1, 1, _D), (7, 10, 1, 1, _D),                # fret marks on the neck
    # guitar body (blocky oval) + soundhole + bridge
    (15, 14, 5, 1, _G), (14, 15, 7, 1, _G), (13, 16, 9, 4, _G),
    (14, 20, 7, 1, _G), (15, 21, 5, 1, _G),
    (16, 17, 2, 2, _K), (15, 19, 4, 1, _D),
    # fretting paw on the neck
    (4, 9, 2, 2, _O),
]


class Cat:
    def __init__(self) -> None:
        self.t = 0.0
        self.state = "idle"
        self._blink = 0.0
        self._notes: list[float] = []
        self._note_acc = 0.0

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            if state != "replying":
                self._notes.clear()

    def update(self, dt: float) -> None:
        self.t += dt
        self._blink = (self._blink + dt) % 4.0
        rate = 4.0 if self.state == "replying" else (1.4 if self.state == "idle" else 0.0)
        if rate:
            self._note_acc += dt * (rate if self.state == "replying" else 0.0)
            while self._note_acc >= 1.0:
                self._note_acc -= 1.0
                self._notes.append(0.0)
        self._notes = [a + dt for a in self._notes]
        self._notes = [a for a in self._notes if a < 1.4]

    # --- drawing ----------------------------------------------------------

    def draw(self, surface, center) -> None:
        ox = center[0] - (_GW * CELL) // 2
        oy = center[1] - (_GH * CELL) // 2

        def px(c, r, w, h, color):
            surface.fill(color, (ox + c * CELL, oy + r * CELL, w * CELL, h * CELL))

        for c, r, w, h, color in _SPRITE:
            px(c, r, w, h, color)

        # Blink: drop a skin-colored bar over the eyes briefly each cycle.
        if self._blink > 3.8:
            px(8, 5, 2, 2, _O)
            px(14, 5, 2, 2, _O)

        # Strumming paw on the guitar body (small bob), consistent in every state.
        period = 0.25 if self.state == "replying" else 0.55
        moving = self.state in ("idle", "replying")
        down = moving and (int(self.t / period) % 2 == 0)
        px(14, 18 if down else 17, 2, 2, _O)

        # Thinking dots above the head.
        if self.state == "thinking":
            n = int(self.t * 3) % 4
            for i in range(3):
                px(19 + i, 2, 1, 1, _W if i < n else _D)

        # Rising music notes when replying.
        for age in self._notes:
            r = 14 - int(age * 9)
            c = 20 + (1 if int(age * 6) % 2 else 0)
            color = _A if age < 1.0 else _D
            px(c, r, 1, 1, color)
            px(c + 1, r - 1, 1, 1, color)

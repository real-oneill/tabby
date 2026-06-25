"""An 8/16-bit pixel-sprite cat playing a guitar.

Everything is drawn as solid blocks snapped to a coarse pixel grid (CELL per sprite
pixel), so it reads as a chunky retro sprite rather than smooth vector art. When the
cat is "replying" it strums and colorful musical notes drift up.
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
_G = (172, 116, 60)          # guitar top (wood)
_GD = (104, 64, 30)          # guitar binding / shadow
_N = (208, 170, 120)         # neck / fretboard
_PEG = (228, 228, 228)       # tuning pegs

_NOTE_COLORS = [theme.RED, theme.YELLOW, theme.GREEN, theme.ACCENT_ALT, theme.MAGENTA, theme.ORANGE]

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

    # --- guitar: fretboard up-left, headstock with pegs ---
    (12, 15, 2, 1, _N), (11, 14, 2, 1, _N), (10, 13, 2, 1, _N), (9, 12, 2, 1, _N),
    (8, 11, 2, 1, _N), (7, 10, 2, 1, _N), (6, 9, 2, 1, _N), (5, 8, 2, 1, _N),
    (9, 12, 1, 1, _GD), (7, 10, 1, 1, _GD),              # frets
    (3, 6, 3, 3, _GD),                                   # headstock
    (3, 6, 1, 1, _PEG), (5, 6, 1, 1, _PEG), (3, 8, 1, 1, _PEG),  # tuning pegs

    # --- guitar: figure-8 body (upper bout / waist / lower bout) ---
    (15, 14, 4, 1, _G), (14, 15, 6, 1, _G),              # upper bout
    (15, 16, 4, 1, _G),                                  # waist
    (13, 17, 8, 3, _G), (14, 20, 6, 1, _G), (15, 21, 4, 1, _G),  # lower bout
    (20, 17, 1, 4, _GD), (14, 21, 7, 1, _GD),            # binding/shadow
    (16, 17, 2, 2, _K),                                  # soundhole
    (14, 19, 5, 1, _GD),                                 # bridge

    # fretting paw on the neck
    (4, 9, 2, 2, _O),
]


class Cat:
    def __init__(self) -> None:
        self.t = 0.0
        self.state = "idle"
        self._blink = 0.0
        self._notes: list[list] = []   # [age, color_index, drift]
        self._spawn = 0.0
        self._note_seq = 0             # monotonic, so colors cycle evenly

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            if state != "replying":
                self._notes.clear()

    def update(self, dt: float) -> None:
        self.t += dt
        self._blink = (self._blink + dt) % 4.0
        if self.state == "replying":
            self._spawn += dt
            while self._spawn >= 0.28:
                self._spawn -= 0.28
                idx = self._note_seq % len(_NOTE_COLORS)
                drift = 1 if self._note_seq % 2 else -1
                self._note_seq += 1
                self._notes.append([0.0, idx, drift])
        for n in self._notes:
            n[0] += dt
        self._notes = [n for n in self._notes if n[0] < 1.6]

    # --- drawing ----------------------------------------------------------

    def draw(self, surface, center) -> None:
        ox = center[0] - (_GW * CELL) // 2
        oy = center[1] - (_GH * CELL) // 2

        def px(c, r, w, h, color):
            surface.fill(color, (ox + c * CELL, oy + r * CELL, w * CELL, h * CELL))

        for c, r, w, h, color in _SPRITE:
            px(c, r, w, h, color)

        # Blink.
        if self._blink > 3.8:
            px(8, 5, 2, 2, _O)
            px(14, 5, 2, 2, _O)

        # Strumming paw over the soundhole (bobs while idle/replying).
        period = 0.22 if self.state == "replying" else 0.55
        moving = self.state in ("idle", "replying")
        down = moving and (int(self.t / period) % 2 == 0)
        px(17, 18 if down else 16, 2, 2, _O)

        # Thinking: a thought bubble rising up-right of the head, dots "..." cycling.
        if self.state == "thinking":
            px(19, 5, 1, 1, _W)            # small connector puff
            px(20, 3, 2, 2, _W)            # larger connector puff
            px(22, -2, 5, 1, _W)           # bubble cloud (rounded)
            px(21, -1, 7, 4, _W)
            px(22, 3, 5, 1, _W)
            n = int(self.t * 3) % 4
            for i in range(3):             # dark dots appear one by one inside it
                px(22 + i * 2, 0, 1, 2, _K if i < n else _W)

        # Colorful musical notes drifting up while answering.
        for age, idx, drift in self._notes:
            color = _NOTE_COLORS[idx]
            c = 18 + drift + int(drift * age * 3)
            r = 15 - int(age * 11)
            self._note_glyph(px, c, r, color)

    @staticmethod
    def _note_glyph(px, c, r, color) -> None:
        px(c, r, 2, 2, color)          # note head
        px(c + 2, r - 3, 1, 4, color)  # stem
        px(c + 2, r - 3, 2, 1, color)  # flag

"""Visual theme: Atari-style palette, fonts, and scaling constants.

Everything is drawn to a small internal surface (INTERNAL_W x INTERNAL_H) and then
nearest-neighbor upscaled by SCALE, so all sizes here are in *internal* pixels.
"""

from __future__ import annotations

import os
from functools import lru_cache

import pygame

# --- Geometry -------------------------------------------------------------

# Internal low-res canvas. The display is 800x480; we render at half that and
# scale x2 for chunky pixels. SCALE is overridable from the command line.
INTERNAL_W = 400
INTERNAL_H = 240
DEFAULT_SCALE = 2


# --- Palette --------------------------------------------------------------
# A curated 16-ish color palette evoking the Atari 2600. Use these names, not
# raw tuples, so the look stays consistent across screens.

BLACK = (24, 16, 16)
DARK = (40, 32, 48)
SHADOW = (64, 52, 72)
WHITE = (236, 236, 236)
GRAY = (152, 148, 156)

RED = (208, 48, 32)
ORANGE = (228, 108, 28)
YELLOW = (224, 196, 64)
GREEN = (56, 176, 72)
CYAN = (64, 188, 188)
BLUE = (60, 92, 204)
PURPLE = (132, 72, 196)
MAGENTA = (204, 60, 132)
BROWN = (132, 84, 36)

# Semantic roles (so screens reference intent, not raw color)
BG = BLACK
PANEL = DARK
PANEL_BORDER = SHADOW
TEXT = WHITE
TEXT_DIM = GRAY
ACCENT = YELLOW
ACCENT_ALT = CYAN
GOOD = GREEN
WARN = ORANGE
BAD = RED

# Per-tool accent colors used for the Home menu tiles and screen headers.
TOOL_COLORS = {
    "tuner": CYAN,
    "metronome": ORANGE,
    "tabs": GREEN,
    "chords": BLUE,
    "assistant": PURPLE,
    "settings": GRAY,
}


# --- Fonts ----------------------------------------------------------------

_FONT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "fonts",
    "PressStart2P-Regular.ttf",
)


@lru_cache(maxsize=None)
def font(size: int) -> pygame.font.Font:
    """Return the pixel font at the given internal-pixel size (cached).

    Press Start 2P is designed for multiples of 8; sizes like 8, 12, 16, 24 read
    cleanly after the x2 upscale.
    """
    if os.path.exists(_FONT_PATH):
        return pygame.font.Font(_FONT_PATH, size)
    # Fallback so the app still runs if the font asset is missing.
    return pygame.font.SysFont("monospace", size, bold=True)


def lerp_color(a, b, t: float):
    """Linear interpolate between two RGB colors. t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )

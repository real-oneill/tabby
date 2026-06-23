"""Manual-speed vertical scroll engine for the text tab player.

Frame-rate independent: ``update(dt)`` advances a float line offset by ``speed``
lines/second while playing. The user dials ``speed`` in by hand (no audio sync) and
can drag to scrub or pan horizontally. This is the core control the player is built
around.
"""

from __future__ import annotations

SPEED_MIN = 0.0
SPEED_MAX = 12.0
SPEED_STEP = 0.5


class TextScroller:
    def __init__(self, line_count: int, speed: float = 2.0) -> None:
        self.line_count = max(0, line_count)
        self.offset = 0.0          # vertical position, in lines (top of viewport)
        self.h_offset = 0.0        # horizontal pan, in pixels
        self.speed = self._clamp_speed(speed)
        self.playing = False
        self._dragging = False

    # --- transport --------------------------------------------------------

    @property
    def max_offset(self) -> float:
        # Allow scrolling until the last line reaches the top of the viewport.
        return float(max(0, self.line_count - 1))

    def toggle(self) -> None:
        self.playing = not self.playing

    def faster(self) -> None:
        self.speed = self._clamp_speed(self.speed + SPEED_STEP)

    def slower(self) -> None:
        self.speed = self._clamp_speed(self.speed - SPEED_STEP)

    def to_top(self) -> None:
        self.offset = 0.0
        self.h_offset = 0.0

    def update(self, dt: float) -> None:
        if self.playing and not self._dragging:
            self.offset += self.speed * dt
            if self.offset >= self.max_offset:
                self.offset = self.max_offset
                self.playing = False  # reached the end

    # --- dragging ---------------------------------------------------------

    def begin_drag(self) -> None:
        self._dragging = True

    def drag_by(self, dx_px: float, dy_px: float, line_h: int) -> None:
        """Pan during a touch drag. ``dy_px``>0 (finger up) scrolls forward."""
        if line_h > 0:
            self.offset = self._clamp_offset(self.offset + dy_px / line_h)
        self.h_offset = max(0.0, self.h_offset + dx_px)

    def end_drag(self) -> None:
        self._dragging = False

    # --- helpers ----------------------------------------------------------

    def _clamp_offset(self, value: float) -> float:
        return max(0.0, min(self.max_offset, value))

    @staticmethod
    def _clamp_speed(value: float) -> float:
        return max(SPEED_MIN, min(SPEED_MAX, round(value, 2)))

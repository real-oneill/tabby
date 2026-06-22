"""Tab player stub. Deepened in a later phase (ASCII first, then Guitar Pro)."""

from __future__ import annotations

from .. import theme
from ..app import Screen
from ..ui.widgets import draw_text


class TabPlayerScreen(Screen):
    title = "TABS"

    def draw(self, surface) -> None:
        cx = theme.INTERNAL_W // 2
        draw_text(surface, "TAB PLAYER", 16, theme.TOOL_COLORS["tabs"], center=(cx, 90))
        draw_text(surface, "COMING SOON", 10, theme.TEXT, center=(cx, 120))
        draw_text(surface, "LIVE SCROLL + A/B LOOP", 8, theme.TEXT_DIM, center=(cx, 150))

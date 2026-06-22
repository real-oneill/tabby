"""Assistant stub. Deepened in a later phase (Databricks AI Gateway)."""

from __future__ import annotations

from .. import theme
from ..app import Screen
from ..ui.widgets import draw_text


class AssistantScreen(Screen):
    title = "ASSISTANT"

    def draw(self, surface) -> None:
        cx = theme.INTERNAL_W // 2
        draw_text(surface, "AI ASSISTANT", 16, theme.TOOL_COLORS["assistant"], center=(cx, 90))
        draw_text(surface, "COMING SOON", 10, theme.TEXT, center=(cx, 120))
        draw_text(surface, "POWERED BY DATABRICKS", 8, theme.TEXT_DIM, center=(cx, 150))

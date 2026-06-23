"""Tab player: browse local .txt tabs, then read them with a manual-speed scroll."""

from __future__ import annotations

import pygame

from .. import theme
from ..app import Screen, TOPBAR_H
from ..tabs import render_text
from ..tabs.library import TabLibrary
from ..tabs.scroller import TextScroller
from ..ui.widgets import Button, draw_text

_PER_PAGE = 7


def _truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "~"


class TabPlayerScreen(Screen):
    title = "TABS"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.library = TabLibrary(app.config.get("tabs_dir"))
        self.entries = []
        self.page = 0
        self.mode = "browse"          # "browse" | "play"
        self.tab = None
        self.scroller: TextScroller | None = None
        self._drag_from = None        # (x, y) during a viewport drag

        # Tab reading viewport + transport buttons (built once, used in play mode).
        self.view = pygame.Rect(8, TOPBAR_H + 4, theme.INTERNAL_W - 16, 176)
        ty = self.view.bottom + 4
        self.transport = [
            Button((8, ty, 50, 26), "LIST", self._to_browse, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
            Button((62, ty, 44, 26), "SPD-", self._slower, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((150, ty, 100, 26), "PLAY", self._toggle_play, color=theme.GOOD, text_color=theme.BLACK, font_size=12),
            Button((294, ty, 44, 26), "SPD+", self._faster, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((344, ty, 48, 26), "TOP", self._to_top, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
        ]
        self._play_btn = self.transport[2]

        # Browse-mode buttons (rebuilt per page in _build_list).
        self.list_buttons: list[Button] = []
        self.pager: list[Button] = []

    # --- Lifecycle --------------------------------------------------------

    def on_enter(self) -> None:
        self.entries = self.library.entries()
        self.page = 0
        self._build_list()

    def on_exit(self) -> None:
        if self.scroller is not None:
            self.app.config.set("scroll_speed", self.scroller.speed)

    # --- Browse mode ------------------------------------------------------

    def _build_list(self) -> None:
        self.list_buttons = []
        start = self.page * _PER_PAGE
        shown = self.entries[start : start + _PER_PAGE]
        y = TOPBAR_H + 8
        for entry in shown:
            self.list_buttons.append(
                Button((12, y, theme.INTERNAL_W - 24, 22), _truncate(entry.name, 40),
                       self._open(entry.path), color=theme.PANEL, text_color=theme.TEXT, font_size=8)
            )
            y += 26

        self.pager = []
        pages = max(1, (len(self.entries) + _PER_PAGE - 1) // _PER_PAGE)
        if pages > 1:
            self.pager = [
                Button((12, 214, 60, 22), "PREV", lambda: self._turn_page(-1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
                Button((theme.INTERNAL_W - 72, 214, 60, 22), "NEXT", lambda: self._turn_page(1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            ]

    def _turn_page(self, delta: int) -> None:
        pages = max(1, (len(self.entries) + _PER_PAGE - 1) // _PER_PAGE)
        self.page = (self.page + delta) % pages
        self._build_list()

    def _open(self, path: str):
        def go() -> None:
            self.tab = self.library.load(path)
            self.scroller = TextScroller(len(self.tab.lines), speed=float(self.app.config.get("scroll_speed")))
            self.app.config.set("last_tab", path)
            self.mode = "play"
            self.title = _truncate(self.tab.display_name.upper(), 18)
        return go

    def _to_browse(self) -> None:
        if self.scroller is not None:
            self.app.config.set("scroll_speed", self.scroller.speed)
        self.mode = "browse"
        self.title = "TABS"

    # --- Play mode --------------------------------------------------------

    def _toggle_play(self) -> None:
        if self.scroller:
            self.scroller.toggle()

    def _slower(self) -> None:
        if self.scroller:
            self.scroller.slower()

    def _faster(self) -> None:
        if self.scroller:
            self.scroller.faster()

    def _to_top(self) -> None:
        if self.scroller:
            self.scroller.to_top()

    # --- Events -----------------------------------------------------------

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        if self.mode == "browse":
            for btn in self.list_buttons:
                btn.handle_event(event, pos)
            for btn in self.pager:
                btn.handle_event(event, pos)
            return

        # Play mode: transport first, then viewport drag-to-scrub.
        for btn in self.transport:
            if btn.handle_event(event, pos):
                return
        self._handle_drag(event, pos)

    def _handle_drag(self, event, pos) -> None:
        if self.scroller is None:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.view.collidepoint(pos):
            self._drag_from = pos
            self.scroller.begin_drag()
        elif event.type == pygame.MOUSEMOTION and self._drag_from is not None:
            dx = self._drag_from[0] - pos[0]   # finger left -> reveal right
            dy = self._drag_from[1] - pos[1]   # finger up -> scroll forward
            self.scroller.drag_by(dx, dy, render_text.line_height())
            self._drag_from = pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._drag_from is not None:
            self._drag_from = None
            self.scroller.end_drag()

    def update(self, dt: float) -> None:
        if self.mode == "play" and self.scroller is not None:
            self.scroller.update(dt)
            self._play_btn.text = "PAUSE" if self.scroller.playing else "PLAY"
            self._play_btn.color = theme.WARN if self.scroller.playing else theme.GOOD

    # --- Draw -------------------------------------------------------------

    def draw(self, surface) -> None:
        if self.mode == "browse":
            self._draw_browse(surface)
        else:
            self._draw_play(surface)

    def _draw_browse(self, surface) -> None:
        if not self.entries:
            cx = theme.INTERNAL_W // 2
            draw_text(surface, "NO TABS FOUND", 12, theme.TEXT, center=(cx, 90))
            draw_text(surface, "DROP .TXT TABS IN", 8, theme.TEXT_DIM, center=(cx, 120))
            draw_text(surface, self.library.tabs_dir, 8, theme.ACCENT_ALT, center=(cx, 134))
            return
        for btn in self.list_buttons:
            btn.draw(surface)
        for btn in self.pager:
            btn.draw(surface)

    def _draw_play(self, surface) -> None:
        if self.tab is None or self.scroller is None:
            return
        render_text.draw(surface, self.tab, self.scroller, self.view)
        for btn in self.transport:
            btn.draw(surface)
        # Speed readout between SPD- and PLAY.
        draw_text(surface, f"{self.scroller.speed:.1f}X", 8, theme.ACCENT, center=(128, self.view.bottom + 17))

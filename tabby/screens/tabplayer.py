"""Tab player: browse local tabs, then read text tabs (manual scroll) or play
Guitar Pro tabs tempo-synced with A/B looping and practice slow-down."""

from __future__ import annotations

import pygame

from .. import theme
from ..app import Screen, TOPBAR_H
from ..tabs import render_synced, render_text
from ..tabs.library import TabLibrary
from ..tabs.scroller import TextScroller
from ..tabs.synced import SyncedPlayer
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
        self.kind = None              # "text" | "synced" while playing
        self.tab = None               # TextTab (text mode)
        self.scroller: TextScroller | None = None
        self.player: SyncedPlayer | None = None
        self._drag_from = None

        self.view = pygame.Rect(8, TOPBAR_H + 4, theme.INTERNAL_W - 16, 176)
        ty = self.view.bottom + 4

        # Text-mode transport.
        self.text_transport = [
            Button((8, ty, 50, 26), "LIST", self._to_browse, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
            Button((62, ty, 44, 26), "SPD-", self._text_slower, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((150, ty, 100, 26), "PLAY", self._text_toggle, color=theme.GOOD, text_color=theme.BLACK, font_size=12),
            Button((294, ty, 44, 26), "SPD+", self._text_faster, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((344, ty, 48, 26), "TOP", self._text_top, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
        ]
        self._text_play_btn = self.text_transport[2]

        # Synced-mode transport (compact single row).
        self.synced_transport = [
            Button((8, ty, 40, 26), "LIST", self._to_browse, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
            Button((52, ty, 38, 26), "SPD-", self._synced_slower, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((94, ty, 70, 26), "PLAY", self._synced_toggle, color=theme.GOOD, text_color=theme.BLACK, font_size=10),
            Button((168, ty, 38, 26), "SPD+", self._synced_faster, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((210, ty, 30, 26), "A", self._synced_a, color=theme.PANEL, text_color=theme.WHITE, font_size=10),
            Button((244, ty, 30, 26), "B", self._synced_b, color=theme.PANEL, text_color=theme.WHITE, font_size=10),
            Button((278, ty, 50, 26), "TRK", self._synced_track, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
            Button((332, ty, 52, 26), "TOP", self._synced_top, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
        ]
        self._synced_play_btn = self.synced_transport[2]
        self._synced_a_btn = self.synced_transport[4]
        self._synced_b_btn = self.synced_transport[5]

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
        y = TOPBAR_H + 8
        for entry in self.entries[start : start + _PER_PAGE]:
            color = theme.ACCENT if entry.kind == "gp" else theme.TEXT
            label = f"{_truncate(entry.name, 34)}  [{'GP' if entry.kind == 'gp' else 'TXT'}]"
            self.list_buttons.append(
                Button((12, y, theme.INTERNAL_W - 24, 22), label, self._open(entry),
                       color=theme.PANEL, text_color=color, font_size=8)
            )
            y += 26

        self.pager = []
        pages = self._page_count()
        if pages > 1:
            self.pager = [
                Button((12, 214, 60, 22), "PREV", lambda: self._turn_page(-1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
                Button((theme.INTERNAL_W - 72, 214, 60, 22), "NEXT", lambda: self._turn_page(1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            ]

    def _page_count(self) -> int:
        return max(1, (len(self.entries) + _PER_PAGE - 1) // _PER_PAGE)

    def _turn_page(self, delta: int) -> None:
        self.page = (self.page + delta) % self._page_count()
        self._build_list()

    def _open(self, entry):
        def go() -> None:
            self.app.config.set("last_tab", entry.path)
            if entry.kind == "gp":
                song = self.library.load_gp(entry.path)
                self.player = SyncedPlayer(song, rate=1.0)
                self.kind = "synced"
                self.title = _truncate(song.display_name.upper(), 18)
            else:
                self.tab = self.library.load_text(entry.path)
                self.scroller = TextScroller(len(self.tab.lines), speed=float(self.app.config.get("scroll_speed")))
                self.kind = "text"
                self.title = _truncate(self.tab.display_name.upper(), 18)
            self.mode = "play"
        return go

    def _to_browse(self) -> None:
        if self.scroller is not None:
            self.app.config.set("scroll_speed", self.scroller.speed)
        self.mode = "browse"
        self.title = "TABS"

    # --- Text transport ---------------------------------------------------

    def _text_toggle(self) -> None:
        if self.scroller:
            self.scroller.toggle()

    def _text_slower(self) -> None:
        if self.scroller:
            self.scroller.slower()

    def _text_faster(self) -> None:
        if self.scroller:
            self.scroller.faster()

    def _text_top(self) -> None:
        if self.scroller:
            self.scroller.to_top()

    # --- Synced transport -------------------------------------------------

    def _synced_toggle(self) -> None:
        if self.player:
            self.player.toggle()

    def _synced_slower(self) -> None:
        if self.player:
            self.player.slower()

    def _synced_faster(self) -> None:
        if self.player:
            self.player.faster()

    def _synced_a(self) -> None:
        if self.player:
            self.player.set_a()

    def _synced_b(self) -> None:
        if self.player:
            self.player.set_b()

    def _synced_track(self) -> None:
        if self.player:
            self.player.cycle_track()

    def _synced_top(self) -> None:
        if self.player:
            self.player.to_start()

    # --- Events -----------------------------------------------------------

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        if self.mode == "browse":
            for btn in (*self.list_buttons, *self.pager):
                btn.handle_event(event, pos)
            return

        transport = self.synced_transport if self.kind == "synced" else self.text_transport
        for btn in transport:
            if btn.handle_event(event, pos):
                return
        self._handle_drag(event, pos)

    def _handle_drag(self, event, pos) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.view.collidepoint(pos):
            self._drag_from = pos
            if self.scroller:
                self.scroller.begin_drag()
        elif event.type == pygame.MOUSEMOTION and self._drag_from is not None:
            dx = self._drag_from[0] - pos[0]
            dy = self._drag_from[1] - pos[1]
            if self.kind == "synced" and self.player:
                self.player.scrub(dx * render_synced.beats_per_pixel())
            elif self.scroller:
                self.scroller.drag_by(dx, dy, render_text.line_height())
            self._drag_from = pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._drag_from is not None:
            self._drag_from = None
            if self.scroller:
                self.scroller.end_drag()

    def update(self, dt: float) -> None:
        if self.mode != "play":
            return
        if self.kind == "synced" and self.player is not None:
            self.player.update(dt)
            self._synced_play_btn.text = "PAUSE" if self.player.playing else "PLAY"
            self._synced_play_btn.color = theme.WARN if self.player.playing else theme.GOOD
            self._synced_a_btn.color = theme.CYAN if self.player.loop_a is not None else theme.PANEL
            self._synced_b_btn.color = theme.MAGENTA if self.player.loop_b is not None else theme.PANEL
        elif self.kind == "text" and self.scroller is not None:
            self.scroller.update(dt)
            self._text_play_btn.text = "PAUSE" if self.scroller.playing else "PLAY"
            self._text_play_btn.color = theme.WARN if self.scroller.playing else theme.GOOD

    # --- Draw -------------------------------------------------------------

    def draw(self, surface) -> None:
        if self.mode == "browse":
            self._draw_browse(surface)
        elif self.kind == "synced":
            self._draw_synced(surface)
        else:
            self._draw_text(surface)

    def _draw_browse(self, surface) -> None:
        if not self.entries:
            cx = theme.INTERNAL_W // 2
            draw_text(surface, "NO TABS FOUND", 12, theme.TEXT, center=(cx, 90))
            draw_text(surface, "DROP .TXT OR .GP FILES IN", 8, theme.TEXT_DIM, center=(cx, 120))
            draw_text(surface, self.library.tabs_dir, 8, theme.ACCENT_ALT, center=(cx, 134))
            return
        for btn in (*self.list_buttons, *self.pager):
            btn.draw(surface)

    def _draw_text(self, surface) -> None:
        if self.tab is None or self.scroller is None:
            return
        render_text.draw(surface, self.tab, self.scroller, self.view)
        for btn in self.text_transport:
            btn.draw(surface)
        draw_text(surface, f"{self.scroller.speed:.1f}X", 8, theme.ACCENT, center=(128, self.view.bottom + 17))

    def _draw_synced(self, surface) -> None:
        if self.player is None:
            return
        render_synced.draw(surface, self.player, self.view)
        # Status line in the empty strip above the top string.
        draw_text(surface, f"{int(self.player.rate * 100)}%", 8, theme.ACCENT, midleft=(self.view.x + 24, self.view.y + 6))
        if self.player.loop_active:
            draw_text(surface, "LOOP", 8, theme.CYAN, center=(self.view.centerx, self.view.y + 6))
        ntracks = len(self.player.song.tracks)
        if ntracks > 1:
            draw_text(surface, f"T{self.player.track_index + 1}/{ntracks}", 8, theme.TEXT_DIM, midright=(self.view.right - 6, self.view.y + 6))
        for btn in self.synced_transport:
            btn.draw(surface)

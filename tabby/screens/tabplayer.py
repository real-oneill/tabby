"""Tab player: browse local tabs or search Songsterr, then read text tabs
(manual scroll) or play Guitar Pro / Songsterr tabs tempo-synced with looping."""

from __future__ import annotations

import threading

import pygame

from .. import theme
from ..app import Screen, TOPBAR_H
from ..tabs import render_synced, render_text, songsterr
from ..tabs.library import TabLibrary
from ..tabs.scroller import TextScroller
from ..tabs.synced import SyncedPlayer
from ..ui.keyboard import Keyboard
from ..ui.widgets import Button, draw_text

_PER_PAGE = 7
_W = theme.INTERNAL_W


def _truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "~"


class TabPlayerScreen(Screen):
    title = "TABS"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.library = TabLibrary(app.config.get("tabs_dir"))
        self.entries = []
        self.page = 0
        self.mode = "browse"          # browse | search | results | tracks | play
        self.kind = None              # text | synced (while playing)
        self.tab = None
        self.scroller: TextScroller | None = None
        self.player: SyncedPlayer | None = None
        self._drag_from = None
        self.error = ""

        # Songsterr search flow state.
        self.kb: Keyboard | None = None
        self.results: list = []
        self.results_page = 0
        self.cur_song = None
        self.track_infos: list = []

        # Background-loading state (so network never freezes the UI).
        self._loading = False
        self._loading_msg = ""
        self._async = None            # ("ok", value) | ("err", message)
        self._async_cb = None

        self.view = pygame.Rect(8, TOPBAR_H + 4, _W - 16, 176)
        ty = self.view.bottom + 4

        self.text_transport = [
            Button((8, ty, 50, 26), "LIST", self._to_browse, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
            Button((62, ty, 44, 26), "SPD-", self._text_slower, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((150, ty, 100, 26), "PLAY", self._text_toggle, color=theme.GOOD, text_color=theme.BLACK, font_size=12),
            Button((294, ty, 44, 26), "SPD+", self._text_faster, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((344, ty, 48, 26), "TOP", self._text_top, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
        ]
        self._text_play_btn = self.text_transport[2]

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

        self.nav_buttons: list[Button] = []   # current mode's list/nav buttons

    # --- Lifecycle --------------------------------------------------------

    def on_enter(self) -> None:
        self.entries = self.library.entries()
        self.page = 0
        self._to_browse()

    def on_exit(self) -> None:
        if self.scroller is not None:
            self.app.config.set("scroll_speed", self.scroller.speed)

    # --- Async helper -----------------------------------------------------

    def _run_async(self, msg: str, fn, on_done) -> None:
        self._loading = True
        self._loading_msg = msg
        self._async = None
        self._async_cb = on_done

        def worker():
            try:
                self._async = ("ok", fn())
            except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
                self._async = ("err", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _pump_async(self) -> None:
        if not self._loading or self._async is None:
            return
        status, payload = self._async
        cb = self._async_cb
        self._loading = False
        self._async = None
        self._async_cb = None
        if status == "ok":
            cb(payload)
        else:
            self.error = _truncate(f"FAILED: {payload}", 46)

    # --- Browse mode ------------------------------------------------------

    def _to_browse(self) -> None:
        if self.scroller is not None:
            self.app.config.set("scroll_speed", self.scroller.speed)
        self.mode = "browse"
        self.title = "TABS"
        self._build_browse()

    def _build_browse(self) -> None:
        self.nav_buttons = [
            Button((12, TOPBAR_H + 8, _W - 24, 22), "* SEARCH SONGSTERR *", self._to_search,
                   color=theme.PURPLE, text_color=theme.WHITE, font_size=8),
        ]
        y = TOPBAR_H + 8 + 28
        start = self.page * 6
        for entry in self.entries[start : start + 6]:
            color = theme.ACCENT if entry.kind == "gp" else theme.TEXT
            label = f"{_truncate(entry.name, 32)}  [{'GP' if entry.kind == 'gp' else 'TXT'}]"
            self.nav_buttons.append(Button((12, y, _W - 24, 22), label, self._open_local(entry),
                                          color=theme.PANEL, text_color=color, font_size=8))
            y += 26
        self._add_pager(len(self.entries), 6, self.page, self._turn_browse)

    def _turn_browse(self, delta: int) -> None:
        pages = max(1, (len(self.entries) + 5) // 6)
        self.page = (self.page + delta) % pages
        self._build_browse()

    def _open_local(self, entry):
        def go() -> None:
            self.app.config.set("last_tab", entry.path)
            if entry.kind == "gp":
                self._start_synced(self.library.load_gp(entry.path))
            else:
                self.tab = self.library.load_text(entry.path)
                self.scroller = TextScroller(len(self.tab.lines), speed=float(self.app.config.get("scroll_speed")))
                self.kind = "text"
                self.title = _truncate(self.tab.display_name.upper(), 18)
                self.mode = "play"
        return go

    # --- Search / results / tracks (Songsterr) ----------------------------

    def _to_search(self) -> None:
        self.error = ""
        self.mode = "search"
        self.title = "SEARCH"
        self.kb = Keyboard(on_submit=self._do_search, on_cancel=self._to_browse, prompt="SONG OR ARTIST")
        self.nav_buttons = []

    def _do_search(self, query: str) -> None:
        self._run_async("SEARCHING", lambda: songsterr.search(query, size=24), self._on_results)

    def _on_results(self, results) -> None:
        self.results = [r for r in results if r.has_player]
        self.results_page = 0
        self.mode = "results"
        self.title = "RESULTS"
        if not self.results:
            self.error = "NO PLAYABLE RESULTS"
        self._build_results()

    def _build_results(self) -> None:
        self.nav_buttons = []
        start = self.results_page * _PER_PAGE
        y = TOPBAR_H + 8
        for r in self.results[start : start + _PER_PAGE]:
            self.nav_buttons.append(Button((12, y, _W - 24, 22), _truncate(r.label.upper(), 42),
                                          self._pick_song(r), color=theme.PANEL, text_color=theme.TEXT, font_size=8))
            y += 26
        self._add_pager(len(self.results), _PER_PAGE, self.results_page, self._turn_results)

    def _turn_results(self, delta: int) -> None:
        pages = max(1, (len(self.results) + _PER_PAGE - 1) // _PER_PAGE)
        self.results_page = (self.results_page + delta) % pages
        self._build_results()

    def _pick_song(self, result):
        def go() -> None:
            self.cur_song = result
            self._run_async("LOADING TRACKS", lambda: songsterr.tracks(result.song_id), self._on_tracks)
        return go

    def _on_tracks(self, infos) -> None:
        # Hide empty tracks; keep playable instrument + vocal tracks.
        self.track_infos = [t for t in infos if not t.is_empty]
        self.mode = "tracks"
        self.title = "PICK TRACK"
        self._build_tracks()

    def _build_tracks(self) -> None:
        self.nav_buttons = []
        y = TOPBAR_H + 8
        for t in self.track_infos[:_PER_PAGE]:
            label = _truncate(f"{t.instrument}: {t.name}".upper(), 42)
            color = theme.TEXT_DIM if t.is_vocal else theme.TEXT
            self.nav_buttons.append(Button((12, y, _W - 24, 22), label, self._pick_track(t),
                                          color=theme.PANEL, text_color=color, font_size=8))
            y += 26

    def _pick_track(self, info):
        def go() -> None:
            sid = self.cur_song.song_id
            self._run_async("LOADING TAB", lambda: songsterr.load_song(sid, info.index), self._start_synced)
        return go

    def _start_synced(self, song) -> None:
        self.player = SyncedPlayer(song, rate=1.0)
        self.kind = "synced"
        self.title = _truncate(song.display_name.upper(), 18)
        self.mode = "play"

    # --- Pager helper -----------------------------------------------------

    def _add_pager(self, count: int, per_page: int, page: int, turn) -> None:
        if count > per_page:
            self.nav_buttons.append(Button((12, 214, 60, 22), "PREV", lambda: turn(-1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8))
            self.nav_buttons.append(Button((_W - 72, 214, 60, 22), "NEXT", lambda: turn(1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8))

    # --- Transport callbacks ---------------------------------------------

    def _text_toggle(self):
        self.scroller and self.scroller.toggle()

    def _text_slower(self):
        self.scroller and self.scroller.slower()

    def _text_faster(self):
        self.scroller and self.scroller.faster()

    def _text_top(self):
        self.scroller and self.scroller.to_top()

    def _synced_toggle(self):
        self.player and self.player.toggle()

    def _synced_slower(self):
        self.player and self.player.slower()

    def _synced_faster(self):
        self.player and self.player.faster()

    def _synced_a(self):
        self.player and self.player.set_a()

    def _synced_b(self):
        self.player and self.player.set_b()

    def _synced_track(self):
        self.player and self.player.cycle_track()

    def _synced_top(self):
        self.player and self.player.to_start()

    # --- Events -----------------------------------------------------------

    def handle_event(self, event, pos) -> None:
        if pos is None or self._loading:
            return
        if self.mode == "search" and self.kb is not None:
            self.kb.handle_event(event, pos)
            return
        if self.mode == "play":
            transport = self.synced_transport if self.kind == "synced" else self.text_transport
            for btn in transport:
                if btn.handle_event(event, pos):
                    return
            self._handle_drag(event, pos)
            return
        # browse / results / tracks: list + nav buttons
        for btn in self.nav_buttons:
            if btn.handle_event(event, pos):
                return

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
        self._pump_async()
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
        if self.mode == "search" and self.kb is not None:
            self.kb.draw(surface)
        elif self.mode == "play":
            self._draw_play(surface)
        else:
            self._draw_list(surface)
        if self.error:
            draw_text(surface, self.error, 8, theme.BAD, center=(_W // 2, 232))
        if self._loading:
            self._draw_loading(surface)

    def _draw_list(self, surface) -> None:
        if self.mode == "browse" and not self.entries and not self.nav_buttons:
            pass
        for btn in self.nav_buttons:
            btn.draw(surface)
        if self.mode == "tracks":
            draw_text(surface, "CHOOSE A PART TO PLAY", 8, theme.TEXT_DIM, center=(_W // 2, 214))

    def _draw_play(self, surface) -> None:
        if self.kind == "synced":
            if self.player is None:
                return
            render_synced.draw(surface, self.player, self.view)
            draw_text(surface, f"{int(self.player.rate * 100)}%", 8, theme.ACCENT, midleft=(self.view.x + 24, self.view.y + 6))
            if self.player.loop_active:
                draw_text(surface, "LOOP", 8, theme.CYAN, center=(self.view.centerx, self.view.y + 6))
            ntracks = len(self.player.song.tracks)
            if ntracks > 1:
                draw_text(surface, f"T{self.player.track_index + 1}/{ntracks}", 8, theme.TEXT_DIM, midright=(self.view.right - 6, self.view.y + 6))
            for btn in self.synced_transport:
                btn.draw(surface)
        else:
            if self.tab is None or self.scroller is None:
                return
            render_text.draw(surface, self.tab, self.scroller, self.view)
            for btn in self.text_transport:
                btn.draw(surface)
            draw_text(surface, f"{self.scroller.speed:.1f}X", 8, theme.ACCENT, center=(128, self.view.bottom + 17))

    def _draw_loading(self, surface) -> None:
        box = pygame.Rect(0, 0, 220, 60)
        box.center = (_W // 2, theme.INTERNAL_H // 2)
        surface.fill(theme.PANEL, box)
        pygame.draw.rect(surface, theme.ACCENT, box, 2)
        draw_text(surface, self._loading_msg + "...", 10, theme.TEXT, center=box.center)

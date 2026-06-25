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

        # Delete-from-list state + confirm modal.
        self.delete_mode = False
        self.pending_delete = None
        modal = pygame.Rect(0, 0, 260, 92)
        modal.center = (_W // 2, theme.INTERNAL_H // 2)
        self.modal_rect = modal
        by = modal.bottom - 32
        self.confirm_buttons = [
            Button((modal.left + 20, by, 100, 24), "CANCEL", self._cancel_delete, color=theme.SHADOW, text_color=theme.WHITE, font_size=10),
            Button((modal.right - 120, by, 100, 24), "DELETE", self._do_delete, color=theme.BAD, text_color=theme.WHITE, font_size=10),
        ]

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
        self.delete_mode = False
        self.pending_delete = None
        self._build_browse()

    def _build_browse(self) -> None:
        self.nav_buttons = [
            Button((12, TOPBAR_H + 8, _W - 94, 22), "* SEARCH SONGSTERR *", self._to_search,
                   color=theme.PURPLE, text_color=theme.WHITE, font_size=8),
            Button((_W - 78, TOPBAR_H + 8, 66, 22), "DONE" if self.delete_mode else "DELETE",
                   self._toggle_delete, color=theme.BAD if self.delete_mode else theme.SHADOW,
                   text_color=theme.WHITE, font_size=8),
        ]
        y = TOPBAR_H + 8 + 28
        start = self.page * 6
        tags = {"gp": "GP", "tabby": "SS", "text": "TXT"}
        colors = {"gp": theme.ACCENT, "tabby": theme.GOOD, "text": theme.TEXT}
        for entry in self.entries[start : start + 6]:
            label = f"{_truncate(entry.name, 32)}  [{tags.get(entry.kind, 'TXT')}]"
            if self.delete_mode:
                callback = self._ask_delete(entry)
                tcolor = theme.BAD if entry.deletable else theme.SHADOW
            else:
                callback = self._open_local(entry)
                tcolor = colors.get(entry.kind, theme.TEXT)
            self.nav_buttons.append(Button((12, y, _W - 24, 22), label, callback,
                                          color=theme.PANEL, text_color=tcolor, font_size=8))
            y += 26
        self._add_pager(len(self.entries), 6, self.page, self._turn_browse)

    # --- Delete from list -------------------------------------------------

    def _toggle_delete(self) -> None:
        self.delete_mode = not self.delete_mode
        self.error = ""
        self._build_browse()

    def _ask_delete(self, entry):
        def go() -> None:
            if entry.deletable:
                self.pending_delete = entry
            else:
                self.error = "BUNDLED SAMPLE - CANNOT DELETE"
        return go

    def _cancel_delete(self) -> None:
        self.pending_delete = None

    def _do_delete(self) -> None:
        entry = self.pending_delete
        self.pending_delete = None
        if entry and self.library.delete(entry.path):
            if self.app.config.get("last_tab") == entry.path:
                self.app.config.set("last_tab", None)
            self.entries = self.library.entries()
            pages = max(1, (len(self.entries) + 5) // 6)
            self.page = min(self.page, pages - 1)
        else:
            self.error = "DELETE FAILED"
        self._build_browse()

    def _turn_browse(self, delta: int) -> None:
        pages = max(1, (len(self.entries) + 5) // 6)
        self.page = (self.page + delta) % pages
        self._build_browse()

    def _open_local(self, entry):
        def go() -> None:
            self.app.config.set("last_tab", entry.path)
            if entry.kind == "gp":
                self._start_synced(self.library.load_gp(entry.path))
            elif entry.kind == "tabby":
                self._start_synced(self.library.load_tabby(entry.path))
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
            self._run_async("LOADING TAB", lambda: songsterr.load_full_song(result.song_id),
                            self._on_song_loaded)
        return go

    def _on_song_loaded(self, song) -> None:
        # Persist to the tabs folder so it's available offline next time.
        from ..tabs import tabbyfmt
        tabbyfmt.save(song, self.app.config.get("tabs_dir"))
        self._start_synced(song)

    def start_query_load(self, query: str) -> None:
        """Search Songsterr for `query` and load the top hit (used by the assistant)."""
        self.error = ""

        def load():
            results = songsterr.search(query, size=5)
            playable = [r for r in results if r.has_player] or results
            if not playable:
                raise RuntimeError("no results")
            return songsterr.load_full_song(playable[0].song_id)

        self._run_async("LOADING TAB", load, self._on_song_loaded)

    def _start_synced(self, song) -> None:
        self.player = SyncedPlayer(song, track_index=getattr(song, "default_track", 0), rate=1.0)
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
        # Delete confirmation takes over input while open.
        if self.pending_delete is not None:
            for btn in self.confirm_buttons:
                if btn.handle_event(event, pos):
                    return
            return
        # browse / results: list + nav buttons
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
        for btn in self.nav_buttons:
            btn.draw(surface)
        if self.mode == "browse" and self.delete_mode and self.pending_delete is None:
            draw_text(surface, "TAP A TAB TO DELETE", 8, theme.BAD, center=(_W // 2, 210))
        if self.pending_delete is not None:
            self._draw_delete_modal(surface)

    def _draw_delete_modal(self, surface) -> None:
        from ..ui.widgets import draw_panel
        draw_panel(surface, self.modal_rect, fill=theme.PANEL, border=theme.BAD, width=2)
        cx = self.modal_rect.centerx
        draw_text(surface, "DELETE THIS TAB?", 10, theme.TEXT, center=(cx, self.modal_rect.top + 20))
        draw_text(surface, _truncate(self.pending_delete.name, 30), 8, theme.TEXT_DIM,
                  center=(cx, self.modal_rect.top + 40))
        for btn in self.confirm_buttons:
            btn.draw(surface)

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

"""Chords & Scales: browse a preloaded library, view fretboard diagrams (cycling
through neck positions), and play along via the synced tab renderer with a click.

Three modes: ``browse`` (paged list, toggle chords/scales) -> ``detail`` (diagram +
position cycling) -> ``play`` (an in-memory TimedSong driven by SyncedPlayer)."""

from __future__ import annotations

import pygame

from .. import theme
from ..app import Screen, TOPBAR_H
from ..audio.click import make_click
from ..chords import library, songbuild
from ..chords.render_diagram import draw_chord
from ..chords.render_neck import draw_neck
from ..tabs import render_synced
from ..tabs.synced import SyncedPlayer
from ..ui.widgets import Button, draw_text

_W = theme.INTERNAL_W
_PER_PAGE = 6

# Browse hierarchy: section (CHORDS / SCALES) -> group -> item list.
# Chord groups filter CHORDS; scale groups (keys are the scale's kind) filter SCALES.
_CHORD_GROUPS = [("MAJOR CHORDS", "MAJOR"), ("MINOR CHORDS", "MINOR"), ("POWER (5TH)", "POWER"),
                 ("7TH CHORDS", "7TH"), ("9TH CHORDS", "9TH")]
_SCALE_GROUPS = [("MINOR PENTATONIC", "min_pent"), ("MAJOR PENTATONIC", "maj_pent"),
                 ("MAJOR SCALE", "major"), ("MIXOLYDIAN", "mixolydian")]


def _chord_group(chord) -> str:
    if chord.category == "5th":
        return "POWER"
    if chord.category == "7th":
        return "7TH"
    if chord.category == "9th":
        return "9TH"
    return "MINOR" if "MINOR" in chord.name else "MAJOR"


class ChordsScalesScreen(Screen):
    title = "CHORDS"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.section = None            # None = top menu; "CHORDS" | "SCALES"
        self.group = None              # None = group menu; else a group/kind key
        self.page = 0
        self.mode = "browse"           # browse | detail | play
        self.selected = None
        self.kind = "chord"            # kind of the selected item
        self.pos_index = 0
        self.chord_mode = "arpeggio"   # arpeggio | strum (chords only)

        self.player: SyncedPlayer | None = None
        self._drag_from = None
        self._prev_pos = 0.0
        self.no_audio = False
        self._click = make_click(accent=False)
        self._accent = make_click(accent=True)

        self.nav_buttons: list[Button] = []
        self.detail_buttons: list[Button] = []

        self.diagram = pygame.Rect(8, TOPBAR_H + 6, _W - 16, 150)
        # Chord boxes start lower so the name/markers sit above them, never overlapping.
        self.chord_area = pygame.Rect(8, TOPBAR_H + 20, _W - 16, 136)
        self.view = pygame.Rect(8, TOPBAR_H + 4, _W - 16, 176)

        # Play-mode transport.
        ty = self.view.bottom + 4
        self.transport = [
            Button((8, ty, 48, 26), "LIST", self._to_detail, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
            Button((60, ty, 44, 26), "SPD-", self._slower, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((150, ty, 100, 26), "PLAY", self._toggle, color=theme.GOOD, text_color=theme.BLACK, font_size=12),
            Button((294, ty, 44, 26), "SPD+", self._faster, color=theme.SHADOW, text_color=theme.WHITE, font_size=8),
            Button((346, ty, 46, 26), "TOP", self._top, color=theme.PANEL, text_color=theme.WHITE, font_size=8),
        ]
        self._play_btn = self.transport[2]

    # --- Lifecycle --------------------------------------------------------

    def on_enter(self) -> None:
        self.no_audio = not self.app.audio.start_output()
        self._to_top()

    def on_exit(self) -> None:
        self.app.audio.stop_output()

    # --- Browse: section (CHORDS/SCALES) -> group -> item list ------------

    def _group_items(self) -> list:
        if self.section == "SCALES":
            return [s for s in library.SCALES if s.kind == self.group]
        return [c for c in library.CHORDS if _chord_group(c) == self.group]

    def _favorite_items(self) -> list:
        cfg = self.app.config
        ch, sc = set(cfg.favorites("chord")), set(cfg.favorites("scale"))
        return ([c for c in library.CHORDS if c.name in ch]
                + [s for s in library.SCALES if s.name in sc])

    def _list_items(self) -> list:
        return self._favorite_items() if self.section == "FAVORITES" else self._group_items()

    def _to_top(self) -> None:
        """Top level: choose CHORDS or SCALES."""
        self.section = None
        self.group = None
        self.page = 0
        self.title = "CHORDS"
        self.mode = "browse"
        self._build_browse()

    def _open_section(self, section: str):
        def go() -> None:
            self.section = section
            self.group = None
            self.page = 0
            self.title = section
            self.mode = "browse"
            self._build_browse()
        return go

    def _to_groups(self) -> None:
        """Back from an item list to the section's group menu."""
        self.group = None
        self.page = 0
        self.mode = "browse"
        self._build_browse()

    def _open_group(self, key: str):
        def go() -> None:
            self.group = key
            self.page = 0
            self.mode = "browse"
            self._build_browse()
        return go

    def _to_list(self) -> None:
        """Return from a diagram to the current group's item list."""
        self.mode = "browse"
        self._build_browse()

    def _build_browse(self) -> None:
        if self.section is None:
            self._build_top()
        elif self.section == "FAVORITES" or self.group is not None:
            self._build_list()
        else:
            self._build_groups()

    def _build_top(self) -> None:
        self.nav_buttons = [
            Button((12, TOPBAR_H + 8, _W - 24, 40), "CHORDS", self._open_section("CHORDS"),
                   color=theme.PANEL, text_color=theme.WHITE, font_size=16),
            Button((12, TOPBAR_H + 54, _W - 24, 40), "SCALES", self._open_section("SCALES"),
                   color=theme.GOOD, text_color=theme.WHITE, font_size=16),
            Button((12, TOPBAR_H + 100, _W - 24, 40), "FAVORITES", self._open_section("FAVORITES"),
                   color=theme.ACCENT, text_color=theme.BLACK, font_size=16),
        ]

    def _build_groups(self) -> None:
        groups = _SCALE_GROUPS if self.section == "SCALES" else _CHORD_GROUPS
        color = theme.GOOD if self.section == "SCALES" else theme.PANEL
        self.nav_buttons = [Button((12, TOPBAR_H + 8, 90, 22), "< BACK", self._to_top,
                                   color=theme.SHADOW, text_color=theme.WHITE, font_size=8)]
        y = TOPBAR_H + 8 + 28
        for label, key in groups:
            self.nav_buttons.append(Button((12, y, _W - 24, 24), label, self._open_group(key),
                                          color=color, text_color=theme.WHITE, font_size=10))
            y += 28

    def _build_list(self) -> None:
        back = self._to_top if self.section == "FAVORITES" else self._to_groups
        self.nav_buttons = [Button((12, TOPBAR_H + 8, 90, 22), "< BACK", back,
                                   color=theme.SHADOW, text_color=theme.WHITE, font_size=8)]
        items = self._list_items()
        start = self.page * _PER_PAGE
        y = TOPBAR_H + 8 + 28
        for item in items[start:start + _PER_PAGE]:
            self.nav_buttons.append(Button((12, y, _W - 24, 22), item.name, self._open_item(item),
                                          color=theme.PANEL, text_color=theme.TEXT, font_size=8))
            y += 26
        if len(items) > _PER_PAGE:
            self.nav_buttons.append(Button((12, 214, 60, 22), "PREV", lambda: self._turn(-1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8))
            self.nav_buttons.append(Button((_W - 72, 214, 60, 22), "NEXT", lambda: self._turn(1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8))

    @staticmethod
    def kind_of(item) -> str:
        return "chord" if isinstance(item, library.Chord) else "scale"

    def _turn(self, delta: int) -> None:
        pages = max(1, (len(self._list_items()) + _PER_PAGE - 1) // _PER_PAGE)
        self.page = (self.page + delta) % pages
        self._build_browse()

    def _open_item(self, item):
        def go() -> None:
            self.selected = item
            self.kind = self.kind_of(item)
            self.title = "SCALES" if self.kind == "scale" else "CHORDS"
            self.pos_index = 0
            self.chord_mode = "arpeggio"
            self._to_detail()
        return go

    # --- Detail -----------------------------------------------------------

    def _to_detail(self) -> None:
        self.mode = "detail"
        self._build_detail_buttons()

    def _build_detail_buttons(self) -> None:
        btns = [Button((8, 182, 46, 26), "LIST", self._to_list, color=theme.PANEL, text_color=theme.WHITE, font_size=8)]
        if self.selected is not None and len(self.selected.positions) > 1:
            btns.append(Button((58, 182, 46, 26), "PREV", lambda: self._cycle_pos(-1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8))
            btns.append(Button((108, 182, 46, 26), "NEXT", lambda: self._cycle_pos(1), color=theme.SHADOW, text_color=theme.WHITE, font_size=8))
        if self.kind == "chord":
            label = "STRUM" if self.chord_mode == "arpeggio" else "ARP"
            btns.append(Button((160, 182, 60, 26), label, self._toggle_chord_mode, color=theme.PANEL, text_color=theme.WHITE, font_size=8))
        fav = self.selected is not None and self.app.config.is_favorite(self.kind, self.selected.name)
        btns.append(Button((226, 182, 56, 26), "* FAV" if fav else "FAV", self._toggle_fav,
                           color=theme.ACCENT if fav else theme.PANEL,
                           text_color=theme.BLACK if fav else theme.WHITE, font_size=8))
        btns.append(Button((_W - 62, 182, 54, 26), "PLAY", self._to_play, color=theme.GOOD, text_color=theme.BLACK, font_size=12))
        self.detail_buttons = btns

    def _toggle_fav(self) -> None:
        if self.selected is not None:
            self.app.config.toggle_favorite(self.kind, self.selected.name)
            self._build_detail_buttons()

    def _cycle_pos(self, delta: int) -> None:
        if self.selected is None:
            return
        n = len(self.selected.positions)
        self.pos_index = (self.pos_index + delta) % n

    def _toggle_chord_mode(self) -> None:
        self.chord_mode = "strum" if self.chord_mode == "arpeggio" else "arpeggio"
        self._build_detail_buttons()

    def open_by_name(self, name: str) -> bool:
        """Jump straight to an item's diagram by name (used by the assistant)."""
        match = library.find_by_name(name)
        if match is None:
            return False
        kind, item = match
        # Set section + group so the diagram's LIST button returns to a sensible list.
        if kind == "scale":
            self.section, self.group = "SCALES", item.kind
        else:
            self.section, self.group = "CHORDS", _chord_group(item)
        self._open_item(item)()
        return True

    # --- Play -------------------------------------------------------------

    def _to_play(self) -> None:
        if self.selected is None:
            return
        pos = self.selected.positions[self.pos_index]
        if self.kind == "scale":
            song = songbuild.scale_song(self.selected, pos)
        else:
            song = songbuild.chord_song(self.selected, pos, mode=self.chord_mode)
        self.player = SyncedPlayer(song, 0, rate=1.0)
        self._prev_pos = 0.0
        self.mode = "play"

    def _toggle(self):
        self.player and self.player.toggle()

    def _slower(self):
        self.player and self.player.slower()

    def _faster(self):
        self.player and self.player.faster()

    def _top(self):
        self.player and self.player.to_start()

    # --- Events -----------------------------------------------------------

    def handle_event(self, event, pos) -> None:
        if pos is None:
            return
        if self.mode == "play":
            for btn in self.transport:
                if btn.handle_event(event, pos):
                    return
            self._handle_drag(event, pos)
            return
        buttons = self.detail_buttons if self.mode == "detail" else self.nav_buttons
        for btn in buttons:
            if btn.handle_event(event, pos):
                return

    def _handle_drag(self, event, pos) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.view.collidepoint(pos):
            self._drag_from = pos
        elif event.type == pygame.MOUSEMOTION and self._drag_from is not None and self.player:
            dx = self._drag_from[0] - pos[0]
            self.player.scrub(dx * render_synced.beats_per_pixel())
            self._drag_from = pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_from = None

    # --- Loop -------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self.mode != "play" or self.player is None:
            return
        self.player.update(dt)
        self._play_btn.text = "PAUSE" if self.player.playing else "PLAY"
        self._play_btn.color = theme.WARN if self.player.playing else theme.GOOD
        # Metronome click on each whole-beat crossing while playing.
        if self.player.playing and int(self.player.pos) != int(self._prev_pos):
            accent = int(self.player.pos) % 4 == 0
            self.app.audio.play_sample(self._accent if accent else self._click)
        self._prev_pos = self.player.pos

    # --- Draw -------------------------------------------------------------

    def draw(self, surface) -> None:
        if self.mode == "browse":
            for btn in self.nav_buttons:
                btn.draw(surface)
            if self.section == "FAVORITES" and not self._favorite_items():
                draw_text(surface, "NO FAVORITES YET", 10, theme.TEXT_DIM, center=(_W // 2, 110))
                draw_text(surface, "STAR A CHORD OR SCALE WITH FAV", 8, theme.TEXT_DIM, center=(_W // 2, 130))
        elif self.mode == "detail":
            self._draw_detail(surface)
        else:
            self._draw_play(surface)

    def _draw_detail(self, surface) -> None:
        item = self.selected
        if item is None:
            return
        pos = item.positions[self.pos_index]
        footer = pos.label
        if len(item.positions) > 1:
            footer = f"{pos.label}  {self.pos_index + 1}/{len(item.positions)}"
        # Name + position label sit above the diagram so neither collides with the
        # chord's X/O markers or the neck's fret numbers. Chord names/labels are short
        # (one top line); scale names are long, so they get two stacked centered lines.
        if self.kind == "chord":
            draw_chord(surface, pos, self.chord_area)
            draw_text(surface, item.name, 10, theme.TEXT, center=(_W // 2, TOPBAR_H + 10))
            draw_text(surface, footer, 8, theme.ACCENT_ALT, midright=(self.diagram.right - 4, TOPBAR_H + 11))
        else:
            draw_neck(surface, pos, self.diagram)
            draw_text(surface, item.name, 8, theme.TEXT, center=(_W // 2, TOPBAR_H + 7))
            draw_text(surface, footer, 8, theme.ACCENT_ALT, center=(_W // 2, TOPBAR_H + 16))
        for btn in self.detail_buttons:
            btn.draw(surface)

    def _draw_play(self, surface) -> None:
        if self.player is None:
            return
        render_synced.draw(surface, self.player, self.view)
        draw_text(surface, f"{int(self.player.rate * 100)}%", 8, theme.ACCENT,
                  midleft=(self.view.x + 24, self.view.y + 6))
        draw_text(surface, self.player.song.title, 8, theme.TEXT_DIM,
                  center=(self.view.centerx, self.view.y + 6))
        if self.no_audio:
            draw_text(surface, "NO AUDIO OUT", 8, theme.BAD, midright=(self.view.right - 6, self.view.y + 6))
        for btn in self.transport:
            btn.draw(surface)

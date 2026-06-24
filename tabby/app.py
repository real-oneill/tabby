"""Application shell: window setup, scene stack, and the scaled main loop."""

from __future__ import annotations

import pygame

from . import theme
from .config import Config
from .audio.engine import AudioEngine
from .ui.widgets import Button, draw_text

TOPBAR_H = 22  # internal pixels reserved for the global top bar


class Screen:
    """Base class for all screens. Subclasses override the hooks they need."""

    title = "TABBY"
    show_back = True

    def __init__(self, app: "App") -> None:
        self.app = app

    def on_enter(self) -> None:  # acquire resources (audio, etc.)
        pass

    def on_exit(self) -> None:  # release resources
        pass

    def handle_event(self, event: pygame.event.Event, pos) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface) -> None:
        pass


class App:
    def __init__(self, fullscreen: bool = False, scale: int = theme.DEFAULT_SCALE) -> None:
        pygame.init()
        pygame.display.set_caption("Tabby")
        self.scale = scale
        flags = pygame.FULLSCREEN | pygame.SCALED if fullscreen else 0
        win_size = (theme.INTERNAL_W * scale, theme.INTERNAL_H * scale)
        self.window = pygame.display.set_mode(win_size, flags)
        # Internal low-res canvas; everything is drawn here then upscaled.
        self.canvas = pygame.Surface((theme.INTERNAL_W, theme.INTERNAL_H))
        self.clock = pygame.time.Clock()
        self.running = True

        self.config = Config()
        self.audio = AudioEngine(self.config)

        # Lazy screen registry: name -> factory. Imported here to avoid cycles.
        from .screens.home import HomeScreen
        from .screens.tuner import TunerScreen
        from .screens.metronome import MetronomeScreen
        from .screens.settings import SettingsScreen
        from .screens.tabplayer import TabPlayerScreen
        from .screens.assistant import AssistantScreen

        self._registry = {
            "home": HomeScreen,
            "tuner": TunerScreen,
            "metronome": MetronomeScreen,
            "settings": SettingsScreen,
            "tabs": TabPlayerScreen,
            "assistant": AssistantScreen,
        }
        self.stack: list[Screen] = []
        self._back_btn = Button(
            (2, 2, 40, TOPBAR_H - 4), "HOME", self.go_back,
            color=theme.SHADOW, text_color=theme.WHITE, font_size=8,
        )
        self.navigate("home")

    # --- Navigation -------------------------------------------------------

    def navigate(self, name: str) -> None:
        screen = self._registry[name](self)
        self.stack.append(screen)
        screen.on_enter()

    def go_back(self) -> None:
        if len(self.stack) > 1:
            screen = self.stack.pop()
            screen.on_exit()

    @property
    def current(self) -> Screen:
        return self.stack[-1]

    def to_internal(self, pos):
        """Convert a window-space mouse position to internal canvas coords."""
        return (pos[0] // self.scale, pos[1] // self.scale)

    # --- Main loop --------------------------------------------------------

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self._handle_events()
            self.current.update(dt)
            self._draw()
        self._shutdown()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if len(self.stack) > 1:
                    self.go_back()
                else:
                    self.running = False
                return
            pos = None
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                pos = self.to_internal(event.pos)
            # Global back button gets first crack at clicks.
            if self._show_back() and pos is not None:
                if self._back_btn.handle_event(event, pos):
                    return
            self.current.handle_event(event, pos)

    def _show_back(self) -> bool:
        return len(self.stack) > 1 and self.current.show_back

    def _draw(self) -> None:
        self.canvas.fill(theme.BG)
        self.current.draw(self.canvas)
        self._draw_topbar()
        # Nearest-neighbor upscale to the window.
        pygame.transform.scale(self.canvas, self.window.get_size(), self.window)
        pygame.display.flip()

    def _draw_topbar(self) -> None:
        bar = pygame.Rect(0, 0, theme.INTERNAL_W, TOPBAR_H)
        self.canvas.fill(theme.PANEL, bar)
        pygame.draw.line(
            self.canvas, theme.PANEL_BORDER, (0, TOPBAR_H), (theme.INTERNAL_W, TOPBAR_H), 1
        )
        draw_text(
            self.canvas, self.current.title, 10, theme.ACCENT,
            center=(theme.INTERNAL_W // 2, TOPBAR_H // 2),
        )
        if self._show_back():
            self._back_btn.draw(self.canvas)

    def _shutdown(self) -> None:
        for screen in reversed(self.stack):
            screen.on_exit()
        self.audio.close()
        pygame.quit()

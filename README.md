# Tabby

A touchscreen-first guitar practice assistant for the Raspberry Pi 5, styled like an
8-bit game with classic Atari colors. Built with Python + Pygame.

Target hardware: Raspberry Pi 5, 5" DSI display (800×480 IPS), USB microphone.

## Tools

- **Tuner** — real-time pitch detection from the mic, with an 8-bit note display.
- **Metronome** — tempo / tap-tempo, time signature, beat-1 accent, synced beat dots.
- **Tab player** — two modes from one browser:
  - **Text tabs** (`.txt`) — manual-speed vertical auto-scroll, play/pause, drag-to-scrub, jump-to-top.
  - **Guitar Pro** (`.gp3/.gp4/.gp5`) — tempo-synced playback with a scrolling time-axis staff,
    practice slow-down, A/B looping, and track select.
- **Assistant** *(coming soon)* — practice help via the Databricks AI Gateway.

### Adding your own tabs

Drop `.txt` or Guitar Pro (`.gp3/.gp4/.gp5`) files into `~/tabby-tabs/` (configurable via
`tabs_dir` in `~/.config/tabby/settings.json`). Public-domain text samples and a generated
Guitar Pro demo ship in `assets/tabs/`. Name files `Artist - Title.ext` to show both.

## Running (dev, on a Mac or the Pi)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py            # 800×480 window; add --fullscreen for the Pi
```

The app renders to a 400×240 internal surface and scales ×2 to 800×480 for chunky pixels.

### Useful flags

- `--fullscreen` — run fullscreen (use on the Pi).
- `--windowed` — force a window (default off-Pi).
- `--scale N` — integer upscale factor (default 2).

## Layout

```
main.py                 entry point
tabby/
  app.py                App + scene manager + scaled main loop
  theme.py              Atari palette, fonts, scaling constants
  config.py             JSON settings persistence
  ui/widgets.py         Button, Label, Needle, BeatDots
  audio/engine.py       sounddevice input/output wrapper
  audio/pitch.py        YIN/autocorrelation pitch detection
  audio/click.py        metronome click generation + scheduler
  tabs/                 text tab model, scroller, renderer, sources, library
  screens/              home, tuner, metronome, settings, tabplayer, assistant
assets/
  fonts/                Press Start 2P
  tabs/                 bundled public-domain sample tabs
  sounds/               generated click samples (optional)
```

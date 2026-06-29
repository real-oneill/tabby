# Tabby

A touchscreen-first guitar practice assistant for the Raspberry Pi 5, styled like an
8-bit game with classic Atari colors. Built with Python + Pygame.

Target hardware: Raspberry Pi 5, 5" DSI display (800×480 IPS), USB microphone.

## Tools

- **Tuner** — real-time pitch detection from the mic, with an 8-bit note display.
- **Metronome** — tempo / tap-tempo, time signature, beat-1 accent, synced beat dots.
- **Tab player** — browse local tabs or search Songsterr, in three flavors:
  - **Text tabs** (`.txt`) — manual-speed vertical auto-scroll, play/pause, drag-to-scrub, jump-to-top.
  - **Guitar Pro** (`.gp3/.gp4/.gp5`) — tempo-synced playback with a scrolling time-axis staff,
    practice slow-down, A/B looping, and track select.
  - **Songsterr search** — on-screen keyboard → search the Songsterr catalog → pick a song and
    track → plays in the same tempo-synced view. Unofficial/personal-use; results are cached in
    `~/.cache/tabby`.
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

## Speaker output (Adafruit I2S bonnet)

For sound on the Pi (metronome + chord/scale play-along click) use an
[Adafruit Speaker Bonnet](https://www.adafruit.com/product/3346) (MAX98357A I2S amp).
Seat it on the 40-pin header, then on the Pi run the included setup script:

```bash
./scripts/setup_speaker.sh   # enables the max98357a device-tree overlay
sudo reboot
./scripts/setup_speaker.sh   # sets the bonnet as the default PipeWire sink
```

Current Raspberry Pi OS runs **PipeWire**, so once the `max98357a` overlay is enabled the
bonnet shows up as an audio sink automatically; the script makes it the **default** sink
(WirePlumber remembers it across reboots) and sets the volume. It also installs
`pipewire-alsa` — Tabby uses `sounddevice`/PortAudio (raw ALSA), and that bridge is what
lets the ALSA `default` reach PipeWire (without it PipeWire owns the cards exclusively and
PortAudio finds no output). Onboard HDMI audio is left intact. Test with
`pw-play /usr/share/sounds/alsa/Front_Center.wav`, adjust with `wpctl set-volume <id> 5%+`.
Tabby needs no change — it outputs to the default device (Settings → **AUDIO OUTPUT =
DEFAULT**); just relaunch with `./scripts/launch.sh`.

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

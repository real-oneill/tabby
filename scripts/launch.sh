#!/bin/bash
# Tabby launcher — used by the Pi's labwc autostart (boot) and for manual relaunch.
# Idempotent: kills any running instance, then launches fullscreen on the Wayland
# session. Env vars default to the Pi's labwc session but honor anything already set.
set -u

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir" || exit 1

# Stop an existing instance so this can double as a restart.
pkill -f "main.py --fullscreen" 2>/dev/null
sleep 1

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-wayland}"

exec ./venv/bin/python main.py --fullscreen

#!/usr/bin/env python3
"""Tabby — guitar practice assistant. Entry point.

Usage:
    python main.py [--fullscreen] [--windowed] [--scale N]
"""

from __future__ import annotations

import argparse
import sys

from tabby import theme
from tabby.app import App


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tabby guitar practice assistant")
    parser.add_argument("--fullscreen", action="store_true", help="run fullscreen (use on the Pi)")
    parser.add_argument("--windowed", action="store_true", help="force windowed mode")
    parser.add_argument("--scale", type=int, default=theme.DEFAULT_SCALE,
                        help="integer upscale factor (default 2)")
    args = parser.parse_args(argv)

    fullscreen = args.fullscreen and not args.windowed
    app = App(fullscreen=fullscreen, scale=max(1, args.scale))
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

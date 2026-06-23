"""Local plain-text tab source: scans directories for ``.txt`` files."""

from __future__ import annotations

import os

from ..textmodel import TextTab, parse_text


def list_files(dirs: list[str], extensions: tuple[str, ...] = (".txt",)) -> list[str]:
    """Return matching paths across ``dirs``, de-duplicated and sorted by name."""
    seen: dict[str, str] = {}  # basename(lower) -> path, so a user file shadows a sample
    for d in dirs:
        d = os.path.expanduser(d)
        if not os.path.isdir(d):
            continue
        for entry in sorted(os.listdir(d)):
            if entry.lower().endswith(extensions):
                seen.setdefault(entry.lower(), os.path.join(d, entry))
    return [seen[k] for k in sorted(seen)]


def load(path: str) -> TextTab:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    stem = os.path.splitext(os.path.basename(path))[0]
    # Preserve an explicit "Artist - Title" filename; otherwise treat _/- as spaces.
    name_hint = stem if " - " in stem else stem.replace("_", " ").replace("-", " ").strip()
    return parse_text(raw, path=path, name_hint=name_hint)

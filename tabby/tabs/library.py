"""Discovery of available tabs across the user's tabs dir and bundled samples."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .sources import local_text

# Bundled sample tabs shipped with the app (repo: assets/tabs).
_BUNDLED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets",
    "tabs",
)


@dataclass
class TabEntry:
    path: str
    name: str


class TabLibrary:
    """Lists text tabs from the configured tabs dir plus the bundled samples."""

    def __init__(self, tabs_dir: str) -> None:
        self.tabs_dir = os.path.expanduser(tabs_dir)

    def _dirs(self) -> list[str]:
        # User dir first so a user's file shadows a same-named bundled sample.
        return [self.tabs_dir, _BUNDLED_DIR]

    def entries(self) -> list[TabEntry]:
        out: list[TabEntry] = []
        for path in local_text.list_files(self._dirs()):
            stem = os.path.splitext(os.path.basename(path))[0]
            name = stem if " - " in stem else stem.replace("_", " ").replace("-", " ").strip()
            out.append(TabEntry(path=path, name=name.upper()))
        return out

    @staticmethod
    def load(path: str):
        return local_text.load(path)

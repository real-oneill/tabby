"""Discovery of available tabs across the user's tabs dir and bundled samples."""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import gp_loader, tabbyfmt
from .sources import local_text

# Bundled sample tabs shipped with the app (repo: assets/tabs).
_BUNDLED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets",
    "tabs",
)

_EXTENSIONS = (".txt", tabbyfmt.EXTENSION) + gp_loader.GP_EXTENSIONS


@dataclass
class TabEntry:
    path: str
    name: str
    kind: str  # "text" | "gp" | "tabby"
    deletable: bool  # True only for files in the user's tabs dir (not bundled samples)


class TabLibrary:
    """Lists text and Guitar Pro tabs from the tabs dir plus bundled samples."""

    def __init__(self, tabs_dir: str) -> None:
        self.tabs_dir = os.path.expanduser(tabs_dir)

    def _dirs(self) -> list[str]:
        # User dir first so a user's file shadows a same-named bundled sample.
        return [self.tabs_dir, _BUNDLED_DIR]

    def entries(self) -> list[TabEntry]:
        out: list[TabEntry] = []
        for path in local_text.list_files(self._dirs(), _EXTENSIONS):
            stem = os.path.splitext(os.path.basename(path))[0]
            name = stem if " - " in stem else stem.replace("_", " ").replace("-", " ").strip()
            deletable = os.path.dirname(path) == self.tabs_dir
            out.append(TabEntry(path=path, name=name.upper(), kind=_kind(path), deletable=deletable))
        return out

    def delete(self, path: str) -> bool:
        """Delete a tab file, but only if it lives in the user's tabs dir."""
        if os.path.dirname(path) != self.tabs_dir:
            return False
        try:
            os.remove(path)
            return True
        except OSError:
            return False

    @staticmethod
    def load_text(path: str):
        return local_text.load(path)

    @staticmethod
    def load_gp(path: str):
        return gp_loader.load(path)

    @staticmethod
    def load_tabby(path: str):
        return tabbyfmt.load(path)


def _kind(path: str) -> str:
    if gp_loader.is_gp_file(path):
        return "gp"
    if path.lower().endswith(tabbyfmt.EXTENSION):
        return "tabby"
    return "text"

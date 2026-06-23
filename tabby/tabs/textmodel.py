"""The plain-text tab model: metadata plus raw monospaced lines (no timing)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextTab:
    """A loaded plain-text tab. ``lines`` are kept verbatim for monospace alignment."""

    title: str
    artist: str
    lines: list[str]
    path: str | None = None

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title

    @property
    def max_line_len(self) -> int:
        return max((len(line) for line in self.lines), default=0)


def parse_text(raw: str, *, path: str | None = None, name_hint: str | None = None) -> TextTab:
    """Build a TextTab from raw file text.

    Tabs are stored verbatim apart from normalizing line endings and expanding any
    literal tab characters (which would otherwise break monospace alignment). Title
    and artist are derived from ``name_hint`` (usually the filename stem); a hint of
    the form ``"Artist - Title"`` is split into the two fields.
    """
    lines = [line.rstrip("\n\r").expandtabs(8) for line in raw.splitlines()]
    # Trim trailing blank lines so scrolling doesn't run off into emptiness.
    while lines and not lines[-1].strip():
        lines.pop()

    artist, title = "", (name_hint or "UNTITLED")
    if name_hint and " - " in name_hint:
        artist, title = (part.strip() for part in name_hint.split(" - ", 1))

    return TextTab(title=title, artist=artist, lines=lines, path=path)

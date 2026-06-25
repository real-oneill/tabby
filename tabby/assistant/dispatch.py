"""Execute the agent's actions against the running app (the 'navigate' capability).

Actions are the small JSON vocabulary the agent emits. Each maps onto existing app
methods, so the assistant can drive the rest of Tabby.
"""

from __future__ import annotations

_SCREENS = {"home", "tuner", "metronome", "tabs", "settings", "assistant"}


def run_actions(app, actions) -> None:
    for action in actions or []:
        if isinstance(action, dict):
            try:
                _run_one(app, action)
            except Exception:  # noqa: BLE001 - one bad action shouldn't break the rest
                pass


def _goto(app, screen: str) -> None:
    if screen not in _SCREENS:
        return
    while len(app.stack) > 1:
        app.go_back()
    if screen != "home":
        app.navigate(screen)


def _run_one(app, action: dict) -> None:
    kind = action.get("type")

    if kind == "navigate":
        _goto(app, action.get("screen", ""))

    elif kind == "set_tempo":
        bpm = max(30, min(300, int(action.get("bpm", 120))))
        app.config.set("tempo", bpm)
        if hasattr(app.current, "metro"):
            app.current.metro.tempo = bpm

    elif kind == "metronome":
        _goto(app, "metronome")
        cur = app.current
        if hasattr(cur, "metro"):
            cur.metro.tempo = int(app.config.get("tempo"))
            cur.metro.start() if action.get("running") else cur.metro.stop()

    elif kind == "search_and_load":
        query = str(action.get("query", "")).strip()
        if query:
            _goto(app, "tabs")
            if hasattr(app.current, "start_query_load"):
                app.current.start_query_load(query)

    # "identify" is handled by the assistant screen itself (shows the song + art),
    # so it is intentionally not dispatched here.

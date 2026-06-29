"""Tabby's AI assistant — a Mosaic AI ChatAgent that runs on Databricks.

The agent answers guitar/practice questions AND drives the Tabby app by emitting a
small set of actions. It calls a Databricks foundation model and returns a strict
``{reply, actions}`` payload. This module is deployed to a Databricks Model Serving
endpoint; it never runs on the Raspberry Pi.
"""

from __future__ import annotations

import json
import re
from typing import Any, Generator

import mlflow
from databricks.sdk import WorkspaceClient
from mlflow.pyfunc import ChatAgent
from mlflow.types.agent import ChatAgentMessage, ChatAgentResponse

# Foundation model that powers the agent (override via the LLM_ENDPOINT param at deploy).
LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"

SYSTEM_PROMPT = """You are Tabby, a friendly guitar-practice assistant built into a small \
8-bit touchscreen device with a tuner, a metronome, and a tab player (local tabs + Songsterr).

You can ANSWER music/practice questions briefly, and you can CONTROL the app with actions.

Respond with ONLY a JSON object, no markdown, of the form:
  {"reply": "<short spoken reply, < 30 words>", "actions": [<action> ...]}

Valid actions:
- {"type": "navigate", "screen": "tuner|metronome|tabs|chords|settings|home"}
- {"type": "set_tempo", "bpm": <integer 40-300>}
- {"type": "metronome", "running": true|false}
- {"type": "search_and_load", "query": "<song and/or artist>"}   // search Songsterr and load the top hit
- {"type": "identify"}                                            // listen to the room and tell the user what song is playing
- {"type": "show_chord", "name": "<chord name>"}                  // open a chord diagram, e.g. "E major", "A7", "E9"
- {"type": "show_scale", "name": "<scale name>"}                  // open a scale diagram, e.g. "E minor pentatonic", "C major"

Rules:
- Use actions only when the user wants to DO something in the app; for pure questions use [].
- "identify what's playing" / "what song is this" -> identify (NOT load a tab).
- "show me / how do I play <chord>" -> show_chord. "<scale> scale" -> show_scale. "open chords" -> navigate chords.
- Combine actions when natural (e.g. set_tempo then metronome running:true).
- Keep "reply" short, friendly, plain text. Never include markdown or code fences."""


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of the model's reply, tolerating stray prose/fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {"reply": text or "Sorry, I didn't catch that.", "actions": []}


class TabbyAgent(ChatAgent):
    def __init__(self, llm_endpoint: str = LLM_ENDPOINT) -> None:
        self.llm_endpoint = llm_endpoint
        self._client = None

    @mlflow.trace(span_type="LLM")
    def _chat(self, messages: list[dict]) -> str:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

        if self._client is None:  # lazy so module import (at log time) needs no auth
            self._client = WorkspaceClient().serving_endpoints
        sdk_messages = [ChatMessage(role=ChatMessageRole(m["role"]), content=m["content"]) for m in messages]
        resp = self._client.query(name=self.llm_endpoint, messages=sdk_messages,
                                  temperature=0.1, max_tokens=400)
        return resp.choices[0].message.content

    @mlflow.trace(span_type="AGENT")
    def predict(self, messages, context=None, custom_inputs=None) -> ChatAgentResponse:
        convo = [{"role": "system", "content": SYSTEM_PROMPT}]
        convo += [{"role": m.role, "content": m.content} for m in messages if m.content]
        raw = self._chat(convo)
        parsed = _extract_json(raw)
        reply = str(parsed.get("reply", "")) or "Okay."
        actions = parsed.get("actions", [])
        if not isinstance(actions, list):
            actions = []
        # Surface the decision on the trace for easy debugging in the MLflow UI.
        span = mlflow.get_current_active_span()
        if span is not None:
            span.set_attribute("actions", actions)
        return ChatAgentResponse(
            messages=[ChatAgentMessage(role="assistant", content=reply, id="1")],
            custom_outputs={"actions": actions},
        )


from mlflow.models import set_model

AGENT = TabbyAgent()
set_model(AGENT)

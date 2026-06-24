"""Client for the Tabby agent deployed on Databricks Model Serving.

Authenticates as a service principal (OAuth M2M, client_credentials) and queries the
agent's serving endpoint. Config/secrets come from the environment or a local file
(`~/.config/tabby/assistant.json`) — never the repo.

Config keys (env override in parentheses):
  host          (TABBY_DATABRICKS_HOST)   e.g. https://dbc-xxxx.cloud.databricks.com
  client_id     (TABBY_SP_CLIENT_ID)
  client_secret (TABBY_SP_SECRET)
  endpoint      (TABBY_AGENT_ENDPOINT)    serving endpoint name, e.g. tabby-assistant
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
import urllib.request

_CONFIG_PATH = os.path.expanduser("~/.config/tabby/assistant.json")
_TIMEOUT = 20            # auth/token
_INVOKE_TIMEOUT = 120    # endpoint query (scale-to-zero cold start can be slow)

# Interim "fm" mode prompt: lets the Pi talk to a foundation-model endpoint directly
# with the same action protocol, before/without the custom agent being deployed. The
# canonical copy lives in agent/tabby_agent.py (which runs on Databricks).
_FM_SYSTEM = """You are Tabby, a friendly guitar-practice assistant on an 8-bit touchscreen \
device with a tuner, metronome, and tab player (local tabs + Songsterr). Answer music/practice \
questions briefly, and control the app with actions. Respond with ONLY a JSON object: \
{"reply":"<short reply, <30 words>","actions":[<action>...]}. Valid actions: \
{"type":"navigate","screen":"tuner|metronome|tabs|settings|home"}, \
{"type":"set_tempo","bpm":<40-300>}, {"type":"metronome","running":true|false}, \
{"type":"search_and_load","query":"<song/artist>"}, {"type":"identify_and_load"}. \
Use actions only for app commands; for pure questions use []. "what song is this"/"identify" \
-> identify_and_load. No markdown."""


class AgentError(RuntimeError):
    pass


def load_config() -> dict:
    cfg: dict = {}
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH) as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            cfg = {}
    env = {
        "host": os.environ.get("TABBY_DATABRICKS_HOST"),
        "client_id": os.environ.get("TABBY_SP_CLIENT_ID"),
        "client_secret": os.environ.get("TABBY_SP_SECRET"),
        "endpoint": os.environ.get("TABBY_AGENT_ENDPOINT"),
    }
    for k, v in env.items():
        if v:
            cfg[k] = v
    if cfg.get("host"):
        cfg["host"] = cfg["host"].rstrip("/")
    return cfg


class AgentClient:
    def __init__(self, config: dict | None = None) -> None:
        self.cfg = config if config is not None else load_config()
        self._token = ""
        self._token_exp = 0.0

    @property
    def configured(self) -> bool:
        return all(self.cfg.get(k) for k in ("host", "client_id", "client_secret", "endpoint"))

    # --- auth -------------------------------------------------------------

    def _bearer(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        auth = base64.b64encode(f"{self.cfg['client_id']}:{self.cfg['client_secret']}".encode()).decode()
        data = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "all-apis"}).encode()
        req = urllib.request.Request(f"{self.cfg['host']}/oidc/v1/token", data=data,
                                    headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                tok = json.load(resp)
        except Exception as exc:  # noqa: BLE001
            raise AgentError(f"auth failed: {exc}") from exc
        self._token = tok["access_token"]
        self._token_exp = time.time() + int(tok.get("expires_in", 3600))
        return self._token

    # --- query ------------------------------------------------------------

    def ask(self, text: str, context: dict | None = None) -> dict:
        """Send a user utterance to the agent; return {'reply': str, 'actions': list}.

        mode "agent" (default): query the deployed custom agent endpoint.
        mode "fm": query a foundation-model endpoint directly with the action protocol.
        """
        if not self.configured:
            raise AgentError("assistant not configured (set ~/.config/tabby/assistant.json)")
        user = text if not context else f"{text}\n\n[app context: {json.dumps(context)}]"
        if self.cfg.get("mode") == "fm":
            body = {"messages": [{"role": "system", "content": _FM_SYSTEM},
                                 {"role": "user", "content": user}],
                    "temperature": 0.1, "max_tokens": 400}
        else:
            body = {"messages": [{"role": "user", "content": user}]}
        url = f"{self.cfg['host']}/serving-endpoints/{self.cfg['endpoint']}/invocations"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
            "Authorization": f"Bearer {self._bearer()}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=_INVOKE_TIMEOUT) as resp:
                data = json.load(resp)
        except Exception as exc:  # noqa: BLE001
            raise AgentError(str(exc)) from exc
        return _parse_response(data)


def _parse_response(data: dict) -> dict:
    """Normalize an agent (ChatAgent) or FM (OpenAI-style) response into {reply, actions}."""
    # Custom agent: {messages:[...], custom_outputs:{actions:[...]}}
    msgs = data.get("messages") or []
    custom = data.get("custom_outputs") or {}
    if msgs or custom:
        reply = msgs[-1].get("content", "") if msgs else ""
        actions = custom.get("actions") if isinstance(custom.get("actions"), list) else []
        if reply or actions:
            return {"reply": reply or "Okay.", "actions": actions}

    # FM-direct: OpenAI {choices:[{message:{content: '<json>'}}]} where content is our protocol.
    if data.get("choices"):
        content = data["choices"][0].get("message", {}).get("content", "")
        return _parse_protocol_json(content)
    return {"reply": "Okay.", "actions": []}


def _parse_protocol_json(content: str) -> dict:
    content = (content or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content[content.find("{"):] if "{" in content else content
    try:
        obj = json.loads(content)
        actions = obj.get("actions")
        return {"reply": str(obj.get("reply", "")) or "Okay.",
                "actions": actions if isinstance(actions, list) else []}
    except (json.JSONDecodeError, AttributeError):
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end > start:
            try:
                obj = json.loads(content[start:end + 1])
                actions = obj.get("actions")
                return {"reply": str(obj.get("reply", "")) or "Okay.",
                        "actions": actions if isinstance(actions, list) else []}
            except json.JSONDecodeError:
                pass
    return {"reply": content or "Sorry, I didn't catch that.", "actions": []}

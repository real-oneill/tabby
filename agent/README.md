# Tabby Agent (runs on Databricks)

The AI assistant's brain. A Mosaic AI **ChatAgent** that answers guitar/practice
questions and drives the Tabby app by emitting actions. It calls a Databricks
foundation model and returns `{reply, actions}`. **This deploys to Databricks Model
Serving and never runs on the Raspberry Pi.**

## Files
- `tabby_agent.py` — the agent (system prompt + action protocol + FM call).
- `deploy.py` — log to MLflow, register to Unity Catalog, deploy a serving endpoint.
- `requirements.txt` — Databricks-side deps (mlflow, databricks-agents, databricks-sdk).

## Action protocol
The agent replies with JSON only:
```json
{"reply": "<short spoken reply>", "actions": [ ... ]}
```
Actions: `navigate(screen)`, `set_tempo(bpm)`, `metronome(running)`,
`search_and_load(query)`, `identify_and_load`.

## Deploy
Easiest is a Databricks notebook (mlflow/databricks-agents are preinstalled):
upload `tabby_agent.py` + `deploy.py`, then run `deploy.py`. It registers
`workspace.default.tabby_assistant` and deploys the `tabby-assistant` endpoint.
Grant the Tabby service principal `CAN_QUERY` on the endpoint.

(Deploying from a laptop also works if `pip install -r requirements.txt` succeeds and
`DATABRICKS_HOST` + `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` are set.)

## Pi client
The Pi (`tabby/assistant/client.py`) authenticates as the service principal (OAuth M2M)
and queries the endpoint. Set `mode: "agent"` + `endpoint: "tabby-assistant"` in
`~/.config/tabby/assistant.json` once deployed. Until then, `mode: "fm"` lets the Pi
talk to a foundation-model endpoint directly with the same action protocol.

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
Runs **inside Databricks** (mlflow/databricks-agents are preinstalled there) — never on
the Pi. `deploy.py` registers the model under the **`tabby` catalog**
(`tabby.assistant.tabby_assistant`) and deploys the `tabby-assistant` serving endpoint
(scale-to-zero, required on Free Edition).

The service principal needs access to the `tabby` catalog first (run as the catalog owner):
```sql
GRANT ALL PRIVILEGES ON CATALOG tabby TO `<sp-application-id>`;
```
Then run `deploy.py` from a Databricks notebook/job (this repo drives it over the Jobs REST
API). Free Edition serverless builds the endpoint container in ~10-20 min.

## Pi client
The Pi (`tabby/assistant/client.py`) authenticates as the service principal (OAuth M2M)
and queries the endpoint. Set `mode: "agent"` + `endpoint: "tabby-assistant"` in
`~/.config/tabby/assistant.json` once deployed. Until then, `mode: "fm"` lets the Pi
talk to a foundation-model endpoint directly with the same action protocol.

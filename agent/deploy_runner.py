"""Drive an agent (re)deploy from a laptop that can't pip-install Databricks deps.

Mac/Pi can't install mlflow/databricks-agents (the Databricks pip proxy is broken),
so this script does the deploy *inside* Databricks: it embeds ``tabby_agent.py`` into a
notebook, uploads it, runs it as a one-off serverless job, and polls to completion.

Auth comes from the same service-principal config the Pi uses:
``~/.config/tabby/assistant.json`` ({host, client_id, client_secret}). No secrets live
in this file. Run:  python agent/deploy_runner.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.expanduser("~/.config/tabby/assistant.json")
NOTEBOOK_PATH = "/Shared/tabby_deploy_runner"


def _cfg() -> dict:
    with open(CFG) as f:
        return json.load(f)


def _token(cfg: dict) -> str:
    data = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "all-apis"}).encode()
    req = urllib.request.Request(f"{cfg['host']}/oidc/v1/token", data=data)
    auth = base64.b64encode(f"{cfg['client_id']}:{cfg['client_secret']}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def _api(host: str, token: str, path: str, payload: dict | None = None, method: str = "POST"):
    url = f"{host}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path} -> {e.code}: {e.read().decode()[:500]}") from None


def _notebook_source() -> str:
    """Build a SOURCE-format Python notebook that embeds the agent and deploys it."""
    with open(os.path.join(HERE, "tabby_agent.py"), "rb") as f:
        agent_b64 = base64.b64encode(f.read()).decode()
    return f'''# Databricks notebook source
# MAGIC %pip install -U mlflow databricks-agents databricks-sdk

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
import base64, json, os, sys
os.makedirs("/tmp/tabbydeploy", exist_ok=True)
with open("/tmp/tabbydeploy/tabby_agent.py", "wb") as f:
    f.write(base64.b64decode("{agent_b64}"))
sys.path.insert(0, "/tmp/tabbydeploy")

import mlflow
from databricks import agents
from databricks.sdk import WorkspaceClient
from mlflow.models.resources import DatabricksServingEndpoint
from tabby_agent import LLM_ENDPOINT

CATALOG, SCHEMA = "tabby", "assistant"
UC_MODEL = f"{{CATALOG}}.{{SCHEMA}}.tabby_assistant"
ENDPOINT = "tabby-assistant"

mlflow.set_registry_uri("databricks-uc")
try:
    WorkspaceClient().schemas.create(name=SCHEMA, catalog_name=CATALOG)
except Exception:
    pass

example = {{"messages": [{{"role": "user", "content": "set the metronome to 90 and start it"}}]}}
with mlflow.start_run(run_name="tabby-assistant"):
    logged = mlflow.pyfunc.log_model(
        name="agent",
        python_model="/tmp/tabbydeploy/tabby_agent.py",
        input_example=example,
        resources=[DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT)],
        pip_requirements=["mlflow", "databricks-sdk", "databricks-agents"],
        registered_model_name=UC_MODEL,
    )
agents.deploy(UC_MODEL, logged.registered_model_version, endpoint_name=ENDPOINT, scale_to_zero=True)
_result = json.dumps({{"ok": True, "version": logged.registered_model_version}})

# COMMAND ----------
dbutils.notebook.exit(_result)
'''


def main() -> None:
    cfg = _cfg()
    host, token = cfg["host"], _token(cfg)
    print(f"host: {host}")

    src_b64 = base64.b64encode(_notebook_source().encode()).decode()
    print(f"uploading notebook -> {NOTEBOOK_PATH}")
    _api(host, token, "/api/2.0/workspace/import", {
        "path": NOTEBOOK_PATH, "format": "SOURCE", "language": "PYTHON",
        "content": src_b64, "overwrite": True,
    })

    print("submitting serverless job run ...")
    run = _api(host, token, "/api/2.1/jobs/runs/submit", {
        "run_name": "tabby-agent-deploy",
        "tasks": [{"task_key": "deploy", "notebook_task": {"notebook_path": NOTEBOOK_PATH}}],
    })
    run_id = run["run_id"]
    print(f"run_id: {run_id}")

    while True:
        time.sleep(20)
        r = _api(host, token, f"/api/2.1/jobs/runs/get?run_id={run_id}", method="GET")
        state = r.get("state", {})
        life, result = state.get("life_cycle_state"), state.get("result_state")
        print(f"  state: {life} {result or ''}".rstrip())
        if life in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            print(f"result_state: {result}")
            print(f"message: {state.get('state_message', '')}")
            # get-output wants the individual task run_id, not the parent run_id.
            task_run_id = r.get("tasks", [{}])[0].get("run_id", run_id)
            out = _api(host, token, f"/api/2.1/jobs/runs/get-output?run_id={task_run_id}", method="GET")
            notebook_out = (out.get("notebook_output") or {}).get("result")
            print(f"notebook_output: {notebook_out}")
            if out.get("error"):
                print(f"error: {out['error'][:1500]}")
            break


if __name__ == "__main__":
    sys.exit(main())

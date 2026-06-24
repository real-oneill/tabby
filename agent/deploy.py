"""Deploy the Tabby agent to a Databricks Model Serving endpoint.

Auth: set DATABRICKS_HOST + DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET
(service-principal M2M OAuth) in the environment, then run:

    python agent/deploy.py

Registers the agent model in the `tabby` Unity Catalog (catalog.schema.model) and
deploys the `tabby-assistant` serving endpoint. The container build takes ~10-20 min.

The service principal needs access to the `tabby` catalog first, e.g.:
    GRANT ALL PRIVILEGES ON CATALOG tabby TO `<sp-application-id>`;
"""

from __future__ import annotations

import os

import mlflow
from databricks import agents
from databricks.sdk import WorkspaceClient
from mlflow.models.resources import DatabricksServingEndpoint

from tabby_agent import LLM_ENDPOINT

# Everything Tabby owns on Databricks lives under the `tabby` catalog.
CATALOG = os.environ.get("TABBY_CATALOG", "tabby")
SCHEMA = os.environ.get("TABBY_SCHEMA", "assistant")
UC_MODEL = os.environ.get("TABBY_UC_MODEL", f"{CATALOG}.{SCHEMA}.tabby_assistant")
ENDPOINT = os.environ.get("TABBY_AGENT_ENDPOINT", "tabby-assistant")
HERE = os.path.dirname(os.path.abspath(__file__))


def _ensure_schema() -> None:
    w = WorkspaceClient()
    try:
        w.schemas.create(name=SCHEMA, catalog_name=CATALOG)
        print(f"Created schema {CATALOG}.{SCHEMA}")
    except Exception:
        pass  # already exists


def main() -> None:
    mlflow.set_registry_uri("databricks-uc")
    _ensure_schema()

    example = {"messages": [{"role": "user", "content": "set the metronome to 90 and start it"}]}

    print(f"Logging + registering {UC_MODEL} ...")
    with mlflow.start_run(run_name="tabby-assistant"):
        logged = mlflow.pyfunc.log_model(
            name="agent",
            python_model=os.path.join(HERE, "tabby_agent.py"),
            input_example=example,
            resources=[DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT)],
            pip_requirements=["mlflow", "databricks-sdk", "databricks-agents"],
            registered_model_name=UC_MODEL,
        )

    print(f"Deploying endpoint '{ENDPOINT}' from {UC_MODEL} v{logged.registered_model_version} ...")
    agents.deploy(UC_MODEL, logged.registered_model_version, endpoint_name=ENDPOINT,
                  scale_to_zero=True)  # Free Edition requires scale-to-zero
    print("Deploy requested. Watch the endpoint come up in the Databricks UI (Serving).")


if __name__ == "__main__":
    main()

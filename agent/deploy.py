"""Deploy the Tabby agent to a Databricks Model Serving endpoint.

Auth: set DATABRICKS_HOST + DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET
(service-principal M2M OAuth) in the environment, then run:

    python agent/deploy.py

Registers `workspace.default.tabby_assistant` in Unity Catalog and deploys the
`tabby-assistant` serving endpoint. The container build takes ~10-20 minutes.
"""

from __future__ import annotations

import os

import mlflow
from databricks import agents
from mlflow.models.resources import DatabricksServingEndpoint

from tabby_agent import LLM_ENDPOINT

UC_MODEL = os.environ.get("TABBY_UC_MODEL", "workspace.default.tabby_assistant")
ENDPOINT = os.environ.get("TABBY_AGENT_ENDPOINT", "tabby-assistant")
HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    mlflow.set_registry_uri("databricks-uc")

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
                  scale_to_zero=True)
    print("Deploy requested. Watch the endpoint come up in the Databricks UI (Serving).")


if __name__ == "__main__":
    main()

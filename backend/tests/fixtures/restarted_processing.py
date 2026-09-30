"""A fresh orchestrator process using public persisted managed-environment state."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from bioimageflow.env_manager import WetlandsEnvManager, configure_wetlands

from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.services.execution import _ExecutionEnvironmentManager
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.tool_environments import ToolEnvironmentService
from tests.fixtures.stale_environment import inventory
from tests.fixtures.stale_worker_numbers import StaleWorkerNumbers
from tests.platform_fixtures import local_registry, worker_chain


def run_worker(manager: Any, results: Path) -> dict[str, Any]:
    registry = local_registry()
    registry._register_tool_from_class(StaleWorkerNumbers, "StaleWorkerNumbers", "e1", "1.0.0")
    graph = worker_chain()
    graph.nodes[1].tool_name = "StaleWorkerNumbers"
    context = ExecutionContext(execution_id="run_e1", workflow_id="e1", draft_revision=1)
    preparations: list[dict[str, Any]] = []
    failures: list[str] = []
    service = ToolEnvironmentService(registry=registry, wetlands_manager=manager)
    adapter = _ExecutionEnvironmentManager(
        manager,
        context=context,
        current_node_id=lambda: "worker",
        on_preparation=lambda preparation, *_args: preparations.append({
            "action": preparation.action,
            "requested_recipe_hash": preparation.requested_recipe_hash,
            "existing_recipe_hash": preparation.existing_recipe_hash,
        }),
        on_provision_event=lambda *_args: None,
        on_ready=lambda *_args: None,
        on_failure=failures.append,
        on_stopped=lambda *_args: None,
        replacement_authorizer=service.can_replace_processing_environment,
    )
    built = build_workflow(graph, registry, storage_path=results)
    assert not built.errors
    built.workflow.get_environment(StaleWorkerNumbers.environment.name).max_workers = 1
    engine = built.workflow.create_engine(resource_lifetime="external", env_manager=adapter)
    try:
        # Match the actual platform whole-workflow dispatch boundary.
        built.workflow.compute(engine=engine)
    finally:
        engine.close()
    store = ResultStoreService(storage_path=results, tool_registry=registry)
    dataframe = store.get_latest_dataframe("worker")
    assert dataframe is not None
    record = store.get_latest_record_dir("worker")
    assert record is not None
    reports = [(record / Path(value)).resolve() for value in dataframe["report"]]
    assert all(report.is_relative_to(record.resolve()) for report in reports)
    return {
        "orchestrator_pid": os.getpid(),
        "worker_pids": dataframe["process_id"].tolist(),
        "values": dataframe["multiplied"].tolist(),
        "reports": [report.read_text() for report in reports],
        "preparations": preparations, "failures": failures,
        "inventory": inventory(),
    }


if __name__ == "__main__":
    root, pixi, results = map(Path, sys.argv[1:])
    configure_wetlands(root=root, pixi_executable=pixi)
    manager = WetlandsEnvManager()
    try:
        print(json.dumps(run_worker(manager, results)))
    finally:
        manager.shutdown_all()
        from bioimageflow.env_manager import get_shared_environment_manager

        get_shared_environment_manager().close()

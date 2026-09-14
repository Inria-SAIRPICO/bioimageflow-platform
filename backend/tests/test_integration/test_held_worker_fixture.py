"""Contract checks for the held real-worker browser fixture."""

import json
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bioimageflow.worker_origins import resolve_worker_tool_origin
from bioimageflow_core import Arguments
from bioimageflow_server.models.graph import ColumnEdge, ToolNodeState
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.tool_registry import ToolRegistryService
from tests.fixtures.held_worker import HeldWorkerNumbers
from tests.graph_factory import graph_state
from tests.platform_fixtures import SourceNumbers


class _CooperativeTask:
    cancel_requested = False
    cancel_calls = 0

    def cancel(self) -> None:
        self.cancel_requested = True
        self.cancel_calls += 1


def test_held_worker_fixture_registers_and_compiles_as_sequential_wetlands(
    tmp_path: Path,
) -> None:
    registry = ToolRegistryService()
    for tool_class in (SourceNumbers, HeldWorkerNumbers):
        registry._register_tool_from_class(
            tool_class,
            tool_class.__name__,
            "bioimageflow-e2e-dynamic",
            "1.0.0",
        )

    metadata = registry.get_tool("HeldWorkerNumbers")
    assert metadata.tool_type == "ProcessingTool"
    assert metadata.row_consumption == "mapped"
    assert set(metadata.inputs) == {"value", "control_port"}
    assert metadata.outputs["multiplied"]["type"] == "int"
    assert HeldWorkerNumbers.environment.name == "platform-worker-numbers"
    assert HeldWorkerNumbers.environment.dependencies == {"python": "3.12"}

    graph = graph_state(
        config={"engine": "wetlands", "execution": "sequential"},
        nodes=[
            ToolNodeState(
                type="tool",
                id="source",
                name="source",
                tool_name="SourceNumbers",
                position=(0, 0),
                parameters={"start": 1, "count": 3},
            ),
            ToolNodeState(
                type="tool",
                id="worker",
                name="worker",
                tool_name="HeldWorkerNumbers",
                position=(200, 0),
                parameters={"control_port": 54321},
            ),
        ],
        edges=[
            ColumnEdge(
                type="column",
                id="source-to-worker",
                source_node="source",
                source_output="value",
                target_node="worker",
                target_input="value",
            )
        ],
    )
    validation = validate_graph(graph, registry, storage_path=tmp_path)
    assert validation.valid, validation.errors
    built = build_workflow(graph, registry, storage_path=tmp_path)
    assert built.errors == []
    assert built.workflow.engine_type == "wetlands"
    assert built.workflow.execution == "sequential"

    origin = resolve_worker_tool_origin(HeldWorkerNumbers)
    assert origin.class_name == "HeldWorkerNumbers"
    assert origin.module == "tests.fixtures.held_worker"


def test_held_worker_acknowledges_cooperative_cancellation_without_output(
    tmp_path: Path,
) -> None:
    task = _CooperativeTask()
    report = tmp_path / "must-not-exist.txt"
    with socket.create_server(("127.0.0.1", 0)) as listener:
        port = listener.getsockname()[1]
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(
                HeldWorkerNumbers().process_row,
                Arguments(value=3, control_port=port, report=report),
                task=task,
            )
            with listener.accept()[0] as control:
                messages = control.makefile("r")
                assert json.loads(messages.readline()) == {
                    "event": "started",
                    "process_id": os.getpid(),
                    "value": 3,
                }
                task.cancel_requested = True
                assert json.loads(messages.readline()) == {
                    "event": "cancellation_observed"
                }
                assert json.loads(messages.readline()) == {
                    "event": "cancellation_acknowledged"
                }
            assert result.result(timeout=1) == []

    assert task.cancel_calls == 1
    assert not report.exists()

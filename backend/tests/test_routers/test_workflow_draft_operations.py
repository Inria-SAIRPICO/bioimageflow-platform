"""Contract tests for recursive workflow draft operation endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import (
    AppConfig,
    InputFieldSchema,
    OutputFieldSchema,
    ToolMetadata,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_draft import WorkflowDraftService
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from bioimageflow_server.ws.handler import ConnectionManager
from tests.graph_factory import graph_document

pytestmark = pytest.mark.anyio


class _ExecutionManager:
    def __init__(self, *, is_running: bool = False) -> None:
        self.is_running = is_running


async def _client(
    tmp_path: Path,
    *,
    is_running: bool = False,
    connection_manager: ConnectionManager | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    registry = ToolRegistryService()
    registry.register_tool(
        "InterfaceTool",
        ToolMetadata(
            name="InterfaceTool",
            display_name="Interface Tool",
            package="test-package",
            package_version="1.0.0",
            tool_type="ProcessingTool",
            row_consumption="mapped",
            inputs={
                "image": InputFieldSchema(
                    type="ImageFile", required=True, connectable="by_default"
                )
            },
            outputs={"mask": OutputFieldSchema(type="ImageFile")},
        ),
    )
    store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
    )
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=_ExecutionManager(is_running=is_running),
            connection_manager=connection_manager,
            storage_path=tmp_path / "bif_data",
            disable_hot_reload=True,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def _create_workflow(client: httpx.AsyncClient, workflow_id: str = "wf") -> None:
    response = await client.post(
        "/api/v1/workflows",
        json={"name": workflow_id, "display_name": workflow_id.split("/")[-1]},
    )
    assert response.status_code == 201


async def test_batch_is_atomic_and_publishes_one_revision(tmp_path: Path) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client)
        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_tool_node",
                        "node_id": "blur_1",
                        "tool_name": "MissingTool",
                        "name": "Blur",
                        "position": [10, 20],
                        "parameters": {"sigma": 2},
                    },
                    {
                        "type": "set_node_enabled",
                        "node_id": "blur_1",
                        "enabled": False,
                    },
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["draft_revision"] == 1
    assert body["graph"]["nodes"][0]["type"] == "tool"
    assert body["graph"]["nodes"][0]["enabled"] is False
    assert len(published) == 1


async def test_nested_scope_addresses_workflow_node_ids(tmp_path: Path) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client)
        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_workflow_node",
                        "node_id": "child_1",
                        "name": "Child",
                        "position": [0, 0],
                        "workflow": graph_document(
                            name="child",
                            display_name="Child",
                            nodes=[
                                {
                                    "type": "tool",
                                    "id": "inner_1",
                                    "name": "Inner",
                                    "tool_name": "MissingTool",
                                    "position": [1, 1],
                                    "parameters": {},
                                }
                            ],
                        ),
                    },
                    {
                        "type": "move_node",
                        "node_id": "inner_1",
                        "position": [30, 40],
                        "scope": {"workflow_path": ["child_1"]},
                    },
                ],
            },
        )

    assert response.status_code == 200
    child = response.json()["graph"]["nodes"][0]
    assert child["type"] == "workflow"
    assert child["workflow"]["nodes"][0]["position"] == [30.0, 40.0]


async def test_interface_operations_use_stable_ids(tmp_path: Path) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client)
        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_tool_node",
                        "node_id": "tool_1",
                        "tool_name": "InterfaceTool",
                        "name": "Tool",
                        "position": [0, 0],
                    },
                    {
                        "type": "expose_workflow_input",
                        "input": {
                            "id": "input-1",
                            "name": "image",
                            "kind": "field",
                            "schema": {"type": "ImageFile"},
                            "targets": [
                                {
                                    "node": "tool_1",
                                    "port": {"kind": "field", "name": "image"},
                                }
                            ],
                        },
                    },
                    {
                        "type": "expose_workflow_output",
                        "output": {
                            "id": "output-1",
                            "name": "mask",
                            "schema": {"type": "ImageFile"},
                            "source": {"node": "tool_1", "column": "mask"},
                        },
                    },
                ],
            },
        )

    assert response.status_code == 200
    interface = response.json()["graph"]["interface"]
    assert interface["inputs"][0]["id"] == "input-1"
    assert interface["outputs"][0]["id"] == "output-1"


async def test_semantic_failure_preserves_revision(tmp_path: Path) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client)
        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_tool_node",
                        "node_id": "n1",
                        "tool_name": "MissingTool",
                        "name": "Node",
                        "position": [0, 0],
                    },
                    {"type": "delete_edge", "edge_id": "missing"},
                ],
            },
        )
        current = await client.get("/api/v1/workflow-drafts/wf")

    assert response.status_code == 422
    assert response.json()["operation_index"] == 1
    assert response.json()["code"] == "missing_edge"
    assert current.json()["draft_revision"] == 0
    assert current.json()["graph"]["nodes"] == []


async def test_nested_deletion_batch_preserves_full_authority_on_failure_and_retries(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )
    child = graph_document(
        name="child",
        interface={"inputs": [
            {"id": port_id, "name": port_id, "kind": "field", "targets": []}
            for port_id in ("input-edge", "input-bound", "input-keep")
        ], "outputs": []},
    )
    graph = graph_document(
        name="wf",
        nodes=[
            {"type": "tool", "id": node_id, "name": node_id,
             "tool_name": "InterfaceTool", "position": [0, 0], "parameters": {}}
            for node_id in ("source", "unrelated")
        ] + [{
            "type": "workflow", "id": "child", "name": "Child", "position": [100, 0],
            "workflow": child,
            "bindings": {
                "input-bound": {"__type__": "int", "value": 7},
                "input-keep": {"__type__": "int", "value": 9},
            },
        }],
        edges=[
            {"type": "column", "id": "removed-edge", "source_node": "source",
             "source_output": "mask", "target_node": "child", "target_input": "input-edge"},
            {"type": "column", "id": "retained-edge", "source_node": "source",
             "source_output": "mask", "target_node": "unrelated", "target_input": "image"},
        ],
    )
    delete_bound = {
        "type": "delete_workflow_input", "input_id": "input-bound",
        "scope": {"workflow_path": ["child"]},
    }
    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client)
        saved = (await client.get("/api/v1/workflows/wf")).json()
        saved_path = Path(saved["info"]["path"])
        # These are structural/control-plane operations, with real endpoint
        # metadata checks; executable scientific validation is not claimed.
        setup = await client.put("/api/v1/workflow-drafts/wf", json={
            "graph": graph, "expected_revision": 0, "validate": False,
        })
        assert setup.status_code == 200, setup.text
        accepted = setup.json()
        store = WorkflowStoreService(saved_path.parent.parent, ToolRegistryService())
        draft_path = store.workflow_dir("wf") / ".bioimageflow" / "draft.json"
        saved_bytes = saved_path.read_bytes()
        draft_bytes = draft_path.read_bytes()
        published.clear()
        failed = await client.post("/api/v1/workflow-draft-operations/wf", json={
            "expected_revision": accepted["draft_revision"], "validate": False,
            "operations": [delete_bound, {"type": "delete_edge", "edge_id": "missing"}],
        })
        assert failed.status_code == 422, failed.text
        assert failed.json()["operation_index"] == 1
        assert failed.json()["code"] == "missing_edge"
        after_failure = (await client.get("/api/v1/workflow-drafts/wf")).json()
        assert after_failure["graph"] == accepted["graph"]
        assert after_failure["draft_revision"] == accepted["draft_revision"]
        assert saved_path.read_bytes() == saved_bytes
        assert draft_path.read_bytes() == draft_bytes
        assert published == []

        succeeded = await client.post("/api/v1/workflow-draft-operations/wf", json={
            "expected_revision": accepted["draft_revision"], "validate": False,
            "operations": [delete_bound, {
                "type": "delete_workflow_input", "input_id": "input-edge",
                "scope": {"workflow_path": ["child"]},
            }],
        })
        assert succeeded.status_code == 200, succeeded.text
        updated = succeeded.json()
        expected_graph = deepcopy(accepted["graph"])
        expected_child = expected_graph["nodes"][2]
        expected_child["workflow"]["interface"]["inputs"] = [
            port for port in expected_child["workflow"]["interface"]["inputs"]
            if port["id"] == "input-keep"
        ]
        del expected_child["bindings"]["input-bound"]
        expected_graph["edges"] = [expected_graph["edges"][1]]
        assert updated["graph"] == expected_graph
        assert updated["draft_revision"] == accepted["draft_revision"] + 1
        assert len(published) == 1
        reloaded = (await client.get("/api/v1/workflow-drafts/wf")).json()
        assert reloaded["graph"] == expected_graph
        assert reloaded["draft_revision"] == updated["draft_revision"]
        reopened = WorkflowDraftService(lambda: store).get_draft_authority_snapshot("wf")
        assert reopened.graph.model_dump(mode="json", by_alias=True) == expected_graph
        assert reopened.draft_revision == updated["draft_revision"]
        assert saved_path.read_bytes() == saved_bytes
        assert draft_path.read_bytes() != draft_bytes


async def test_stale_revision_and_execution_lock_are_machine_readable(
    tmp_path: Path,
) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client)
        first = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_tool_node",
                        "node_id": "n1",
                        "tool_name": "MissingTool",
                        "name": "Node",
                        "position": [0, 0],
                    }
                ],
            },
        )
        stale = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [{"type": "delete_node", "node_id": "n1"}],
            },
        )
    assert first.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["error"] == "draft_revision_conflict"

    async for locked_client in _client(tmp_path / "locked", is_running=True):
        await _create_workflow(locked_client)
        locked = await locked_client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [{"type": "delete_node", "node_id": "n1"}],
            },
        )
    assert locked.status_code == 423
    assert locked.json()["error"] == "workflow_locked"

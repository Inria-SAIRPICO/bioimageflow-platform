"""Contract tests for recursive workflow draft operation endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
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
        storage_base_dir=tmp_path / "workspace" / "outputs",
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

"""Tests for semantic workflow draft operation endpoints."""

from __future__ import annotations

import json
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

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
                    type="ImageFile",
                    required=True,
                    connectable="by_default",
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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _create_workflow(client: httpx.AsyncClient, name: str = "wf") -> None:
    response = await client.post(
        "/api/v1/workflows",
        json={"name": name, "display_name": name.split("/")[-1]},
    )
    assert response.status_code == 201


def _draft_path(tmp_path: Path, workflow_id: str = "wf") -> Path:
    return tmp_path / "workspace" / "workflows" / workflow_id / ".bioimageflow" / "draft.json"


def _agent_state_path(tmp_path: Path) -> Path:
    return tmp_path / "workspace" / ".bioimageflow" / "agent-state.json"


async def test_operation_api_applies_batch_and_publishes_once(tmp_path: Path) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
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
    assert body["workflow_id"] == "wf"
    assert body["draft_revision"] == 1
    assert body["updated_by"] == "agent"
    assert body["dirty_against_saved"] is True
    assert body["validation"]["valid"] is False
    assert body["graph"]["nodes"][0]["id"] == "blur_1"
    assert body["graph"]["nodes"][0]["enabled"] is False
    assert json.loads(_draft_path(tmp_path).read_text())["draft_revision"] == 1
    assert json.loads(_agent_state_path(tmp_path).read_text())["current_draft_revision"] == 1
    assert published == [
        {
            "workflow_id": "wf",
            "draft_revision": 1,
            "updated_by": "agent",
            "updated_at": body["updated_at"],
            "dirty_against_saved": True,
        }
    ]


async def test_operation_api_applies_published_interface_edits_once(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "input_1",
                        "tool_name": "InterfaceTool",
                        "name": "Input",
                        "position": [0, 0],
                        "parameters": {},
                    },
                    {
                        "type": "set_published_input",
                        "name": "image",
                        "internal_node_id": "input_1",
                        "internal_field": "image",
                        "kind": "input",
                        "schema": {"type": "ImageFile"},
                    },
                    {
                        "type": "set_published_output",
                        "name": "mask",
                        "internal_node_id": "input_1",
                        "internal_output": "mask",
                        "schema": {"type": "ImageFile"},
                    },
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["draft_revision"] == 1
    assert body["graph"]["published_inputs"] == [
        {
            "name": "image",
            "internal_node_id": "input_1",
            "internal_field": "image",
            "kind": "input",
            "schema": {"type": "ImageFile"},
            "default": None,
        }
    ]
    assert body["graph"]["published_outputs"] == [
        {
            "name": "mask",
            "internal_node_id": "input_1",
            "internal_output": "mask",
            "schema": {"type": "ImageFile"},
        }
    ]
    assert json.loads(_draft_path(tmp_path).read_text())["draft_revision"] == 1
    assert len(published) == 1


async def test_operation_api_applies_move_nodes_once(tmp_path: Path) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "a",
                        "tool_name": "MissingTool",
                        "name": "A",
                        "position": [0, 0],
                        "parameters": {},
                    },
                    {
                        "type": "create_node",
                        "node_id": "b",
                        "tool_name": "MissingTool",
                        "name": "B",
                        "position": [0, 0],
                        "parameters": {},
                    },
                    {
                        "type": "move_nodes",
                        "moves": [
                            {"node_id": "a", "position": [100, 120]},
                            {"node_id": "b", "position": [300, 120]},
                        ],
                    },
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert [(node["id"], node["position"]) for node in body["graph"]["nodes"]] == [
        ("a", [100, 120]),
        ("b", [300, 120]),
    ]
    assert json.loads(_draft_path(tmp_path).read_text())["draft_revision"] == 1
    assert len(published) == 1


async def test_operation_api_applies_scoped_layout_once(tmp_path: Path) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")
        put_response = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "expected_revision": 0,
                "graph": {
                    "nodes": [
                        {
                            "id": "outer",
                            "name": "Outer",
                            "tool_name": "__sub_workflow__",
                            "position": [0, 0],
                            "parameters": {},
                            "sub_workflow": {
                                "nodes": [
                                    {
                                        "id": "inner",
                                        "name": "Inner",
                                        "tool_name": "MissingTool",
                                        "position": [1, 1],
                                        "parameters": {},
                                    }
                                ],
                                "edges": [],
                            },
                        },
                        {
                            "id": "inner",
                            "name": "Root Inner",
                            "tool_name": "MissingTool",
                            "position": [9, 9],
                            "parameters": {},
                        },
                    ],
                    "edges": [],
                },
            },
        )
        assert put_response.status_code == 200

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 1,
                "operations": [
                    {
                        "type": "move_node",
                        "node_id": "inner",
                        "position": [100, 120],
                        "scope": {"sub_workflow_path": ["outer"]},
                    },
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["graph"]["nodes"][0]["sub_workflow"]["nodes"][0]["position"] == [
        100,
        120,
    ]
    assert body["graph"]["nodes"][1]["position"] == [9, 9]
    assert json.loads(_draft_path(tmp_path).read_text())["draft_revision"] == 2
    assert len(published) == 2


async def test_operation_api_preserves_nested_workflow_ids(tmp_path: Path) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client, "folder/wf")

        response = await client.post(
            "/api/v1/workflow-draft-operations/folder/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "n1",
                        "tool_name": "MissingTool",
                        "name": "Node",
                        "position": [0, 0],
                        "parameters": {},
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["workflow_id"] == "folder/wf"


async def test_operation_api_uses_expected_revision_conflict_response(
    tmp_path: Path,
) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client, "wf")
        first = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "n1",
                        "tool_name": "MissingTool",
                        "name": "Node",
                        "position": [0, 0],
                        "parameters": {},
                    }
                ],
            },
        )
        assert first.status_code == 200

        stale = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [{"type": "rename_node", "node_id": "n1", "name": "New"}],
            },
        )

    assert stale.status_code == 409
    assert stale.json()["error"] == "draft_revision_conflict"
    assert stale.json()["current_revision"] == 1


async def test_operation_api_rejects_locked_workflow_without_write(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, is_running=True, connection_manager=manager):
        await _create_workflow(client, "wf")
        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "n1",
                        "tool_name": "MissingTool",
                        "name": "Node",
                        "position": [0, 0],
                        "parameters": {},
                    }
                ],
            },
        )

    assert response.status_code == 423
    assert response.json()["error"] == "workflow_locked"
    assert not _draft_path(tmp_path).exists()
    assert published == []


async def test_operation_api_reports_missing_workflow(tmp_path: Path) -> None:
    async for client in _client(tmp_path):
        response = await client.post(
            "/api/v1/workflow-draft-operations/missing",
            json={
                "expected_revision": 0,
                "operations": [{"type": "delete_node", "node_id": "n1"}],
            },
        )

    assert response.status_code == 404


async def test_operation_validation_failure_is_atomic(tmp_path: Path) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")
        initial = await client.get("/api/v1/workflow-drafts/wf")
        assert initial.status_code == 200
        initial_state = _agent_state_path(tmp_path).read_text()

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "n1",
                        "tool_name": "MissingTool",
                        "name": "Node",
                        "position": [0, 0],
                        "parameters": {},
                    },
                    {"type": "delete_edge", "edge_id": "missing"},
                ],
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": "operation_validation_error",
        "operation_index": 1,
        "code": "missing_edge",
        "detail": "Edge not found: missing",
    }
    assert not _draft_path(tmp_path).exists()
    assert _agent_state_path(tmp_path).read_text() == initial_state
    assert published == []


async def test_published_interface_validation_failure_is_atomic(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")
        initial = await client.get("/api/v1/workflow-drafts/wf")
        assert initial.status_code == 200
        initial_state = _agent_state_path(tmp_path).read_text()

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "input_1",
                        "tool_name": "MissingTool",
                        "name": "Input",
                        "position": [0, 0],
                        "parameters": {},
                    },
                    {
                        "type": "set_published_input",
                        "name": "image",
                        "internal_node_id": "missing",
                        "internal_field": "image",
                        "kind": "input",
                        "schema": {"type": "ImageFile"},
                    },
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["operation_index"] == 1
    assert response.json()["code"] == "missing_node"
    assert not _draft_path(tmp_path).exists()
    assert _agent_state_path(tmp_path).read_text() == initial_state
    assert published == []


async def test_published_interface_metadata_failure_is_atomic(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")
        initial = await client.get("/api/v1/workflow-drafts/wf")
        assert initial.status_code == 200
        initial_state = _agent_state_path(tmp_path).read_text()

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "input_1",
                        "tool_name": "InterfaceTool",
                        "name": "Input",
                        "position": [0, 0],
                        "parameters": {},
                    },
                    {
                        "type": "set_published_input",
                        "name": "typo",
                        "internal_node_id": "input_1",
                        "internal_field": "iamge",
                        "kind": "input",
                        "schema": {"type": "ImageFile"},
                    },
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["operation_index"] == 1
    assert response.json()["code"] == "missing_published_input_target"
    assert not _draft_path(tmp_path).exists()
    assert _agent_state_path(tmp_path).read_text() == initial_state
    assert published == []


async def test_move_nodes_validation_failure_is_atomic(tmp_path: Path) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")
        initial = await client.get("/api/v1/workflow-drafts/wf")
        assert initial.status_code == 200
        initial_state = _agent_state_path(tmp_path).read_text()

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "a",
                        "tool_name": "MissingTool",
                        "name": "A",
                        "position": [0, 0],
                        "parameters": {},
                    },
                    {
                        "type": "move_nodes",
                        "moves": [
                            {"node_id": "a", "position": [100, 120]},
                            {"node_id": "missing", "position": [300, 120]},
                        ],
                    },
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["operation_index"] == 1
    assert response.json()["code"] == "missing_node"
    assert not _draft_path(tmp_path).exists()
    assert _agent_state_path(tmp_path).read_text() == initial_state
    assert published == []


async def test_scoped_layout_validation_failure_is_atomic(tmp_path: Path) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []
    manager.publish_workflow_draft_changed = (  # type: ignore[method-assign]
        lambda **payload: published.append(payload)
    )

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")
        put_response = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "expected_revision": 0,
                "graph": {
                    "nodes": [
                        {
                            "id": "plain",
                            "name": "Plain",
                            "tool_name": "MissingTool",
                            "position": [0, 0],
                            "parameters": {},
                        }
                    ],
                    "edges": [],
                },
            },
        )
        assert put_response.status_code == 200
        before = _draft_path(tmp_path).read_text()
        agent_state_before = _agent_state_path(tmp_path).read_text()
        published.clear()

        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 1,
                "operations": [
                    {
                        "type": "move_node",
                        "node_id": "inner",
                        "position": [100, 120],
                        "scope": {"sub_workflow_path": ["plain"]},
                    },
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["operation_index"] == 0
    assert response.json()["code"] == "missing_sub_workflow"
    assert _draft_path(tmp_path).read_text() == before
    assert _agent_state_path(tmp_path).read_text() == agent_state_before
    assert published == []


async def test_operation_validation_failure_preserves_existing_draft_file(
    tmp_path: Path,
) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client, "wf")
        first = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "node_id": "n1",
                        "tool_name": "MissingTool",
                        "name": "Node",
                        "position": [0, 0],
                        "parameters": {},
                    }
                ],
            },
        )
        assert first.status_code == 200
        before = _draft_path(tmp_path).read_text()
        agent_state_before = _agent_state_path(tmp_path).read_text()

        failed = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={
                "expected_revision": 1,
                "operations": [
                    {"type": "rename_node", "node_id": "n1", "name": "Changed"},
                    {"type": "delete_edge", "edge_id": "missing"},
                ],
            },
        )

    assert failed.status_code == 422
    assert _draft_path(tmp_path).read_text() == before
    assert _agent_state_path(tmp_path).read_text() == agent_state_before


async def test_operation_api_enforces_batch_model_before_transform(
    tmp_path: Path,
) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client, "wf")
        response = await client.post(
            "/api/v1/workflow-draft-operations/wf",
            json={"expected_revision": 0, "operations": []},
        )

    assert response.status_code == 422
    assert not _draft_path(tmp_path).exists()


async def test_full_dag_draft_api_still_works(tmp_path: Path) -> None:
    async for client in _client(tmp_path):
        await _create_workflow(client, "wf")
        put_response = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "expected_revision": 0,
                "updated_by": "frontend",
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "name": "Node",
                            "tool_name": "MissingTool",
                            "position": [0, 0],
                            "parameters": {},
                        }
                    ],
                    "edges": [],
                },
            },
        )
        get_response = await client.get("/api/v1/workflow-drafts/wf")

    assert put_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["graph"]["nodes"][0]["id"] == "n1"

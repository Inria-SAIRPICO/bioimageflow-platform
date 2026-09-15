"""Contract tests for private nested-workflow snapshot routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.models.viewer_preferences import (
    SessionOutputPreferenceKey,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.viewer_preferences import (
    ViewerPreferenceStore,
    ensure_workspace_identity,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from tests.graph_factory import graph_document

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _ExecutionManager:
    def __init__(self) -> None:
        self.is_running = False


def _graph(
    node_id: str,
    input_name: str = "image",
) -> dict[str, Any]:
    return graph_document(
        name=f"{node_id}_workflow",
        display_name=f"{node_id} workflow",
        nodes=[
            {
                "type": "tool",
                "id": node_id,
                "name": node_id,
                "tool_name": "MissingTool",
                "position": [0, 0],
                "parameters": {},
            }
        ],
        interface={
            "inputs": [
                {
                    "id": "input-1",
                    "name": input_name,
                    "kind": "field",
                    "schema": {"type": "Path"},
                    "targets": [
                        {
                            "node": node_id,
                            "port": {"kind": "field", "name": "image"},
                        }
                    ],
                }
            ],
            "outputs": [],
        },
    )


def _graph_with_output(node_id: str) -> dict[str, Any]:
    graph = _graph(node_id)
    graph["nodes"][0]["viewer_additions"] = {"image": {"napari": None}}
    return graph


def _parent_graph(parent_node_id: str, child: dict[str, Any]) -> dict[str, Any]:
    return graph_document(
        name="parent",
        display_name="Parent",
        nodes=[
            {
                "type": "workflow",
                "id": parent_node_id,
                "name": "Child",
                "position": [0, 0],
                "workflow": child,
                "bindings": {},
            }
        ],
    )


@pytest.fixture
async def client_and_manager(
    tmp_path: Path,
) -> AsyncIterator[
    tuple[
        httpx.AsyncClient,
        _ExecutionManager,
        WorkflowStoreService,
        ViewerPreferenceStore,
    ]
]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
    )
    manager = _ExecutionManager()
    preferences = ViewerPreferenceStore(tmp_path / "viewer-preferences.json")
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=manager,
            viewer_preference_store=preferences,
            storage_path=tmp_path / "outputs",
            disable_hot_reload=True,
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for name in ("root-a", "root-b"):
            response = await client.post(
                "/api/v1/workflows",
                json={"name": name, "display_name": name},
            )
            assert response.status_code == 201
        yield client, manager, store, preferences


async def test_open_replace_get_and_revision_checked_delete(
    client_and_manager: tuple[
        httpx.AsyncClient,
        _ExecutionManager,
        WorkflowStoreService,
        ViewerPreferenceStore,
    ],
) -> None:
    client, _, _, _ = client_and_manager
    opened = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:root-a",
                "workflow_id": "root-a",
            },
            "parent_node_id": "child_1",
            "graph": _graph("inner"),
        },
    )
    assert opened.status_code == 201
    snapshot = opened.json()
    assert snapshot["graph"]["name"] == "inner_workflow"

    replaced = await client.put(
        f"/api/v1/nested-workflow-snapshots/{snapshot['session_id']}",
        json={
            "expected_revision": snapshot["snapshot_revision"],
            "graph": _graph("inner", "renamed"),
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["snapshot_revision"] == 1
    assert replaced.json()["graph"]["interface"]["inputs"][0]["name"] == "renamed"

    recovered = await client.get(
        f"/api/v1/nested-workflow-snapshots/{snapshot['session_id']}"
    )
    assert recovered.json() == replaced.json()

    stale = await client.delete(
        f"/api/v1/nested-workflow-snapshots/{snapshot['session_id']}",
        params={"expected_revision": 0},
    )
    assert stale.status_code == 409
    deleted = await client.delete(
        f"/api/v1/nested-workflow-snapshots/{snapshot['session_id']}",
        params={"expected_revision": 1},
    )
    assert deleted.status_code == 204


async def test_mutations_return_423_without_changing_the_record(
    client_and_manager: tuple[
        httpx.AsyncClient,
        _ExecutionManager,
        WorkflowStoreService,
        ViewerPreferenceStore,
    ],
) -> None:
    client, manager, store, _ = client_and_manager
    opened = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:root-a",
                "workflow_id": "root-a",
            },
            "parent_node_id": "child_1",
            "graph": _graph("inner"),
        },
    )
    snapshot = opened.json()
    path = (
        store.workspace_dir
        / ".bioimageflow"
        / "nested-workflow-snapshots"
        / f"{snapshot['session_id']}.json"
    )
    before = path.read_bytes()
    manager.is_running = True

    replace = await client.put(
        f"/api/v1/nested-workflow-snapshots/{snapshot['session_id']}",
        json={"expected_revision": 0, "graph": _graph("inner", "blocked")},
    )
    delete = await client.delete(
        f"/api/v1/nested-workflow-snapshots/{snapshot['session_id']}",
        params={"expected_revision": 0},
    )
    other_open = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:root-b",
                "workflow_id": "root-b",
            },
            "parent_node_id": "child_1",
            "graph": _graph("other"),
        },
    )

    assert [replace.status_code, delete.status_code, other_open.status_code] == [423, 423, 423]
    assert path.read_bytes() == before
    assert len(list(path.parent.glob("*.json"))) == 1


async def test_delete_rejects_orphaning_a_nested_snapshot(
    client_and_manager: tuple[
        httpx.AsyncClient,
        _ExecutionManager,
        WorkflowStoreService,
        ViewerPreferenceStore,
    ],
) -> None:
    client, _, _, _ = client_and_manager
    parent_response = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:root-a",
                "workflow_id": "root-a",
            },
            "parent_node_id": "child_1",
            "graph": _graph("inner"),
        },
    )
    parent = parent_response.json()
    child_response = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {"kind": "nested", "session_id": parent["session_id"]},
            "parent_node_id": "child_2",
            "graph": _graph("deep_inner"),
        },
    )
    child = child_response.json()

    rejected = await client.delete(
        f"/api/v1/nested-workflow-snapshots/{parent['session_id']}",
        params={"expected_revision": parent["snapshot_revision"]},
    )
    child_update = await client.put(
        f"/api/v1/nested-workflow-snapshots/{child['session_id']}",
        json={
            "expected_revision": child["snapshot_revision"],
            "graph": _graph("deep_inner", "still_editable"),
        },
    )

    assert rejected.status_code == 409
    assert rejected.json() == {
        "error": "nested_snapshot_has_dependents",
        "detail": (
            f"Cannot delete nested snapshot {parent['session_id']}: 1 dependent "
            "nested snapshot must be deleted first"
        ),
        "dependent_session_ids": [child["session_id"]],
    }
    assert child_update.status_code == 200

    openapi = (await client.get("/openapi.json")).json()
    conflict_schema = openapi["paths"][
        "/api/v1/nested-workflow-snapshots/{session_id}"
    ]["delete"]["responses"]["409"]["content"]["application/json"]["schema"]
    assert {item["$ref"] for item in conflict_schema["anyOf"]} == {
        "#/components/schemas/NestedWorkflowSnapshotConflictResponse",
        "#/components/schemas/NestedWorkflowSnapshotDependencyConflictResponse",
    }


async def test_finalize_root_preferences_requires_accepted_graph_and_is_retryable(
    client_and_manager: tuple[
        httpx.AsyncClient,
        _ExecutionManager,
        WorkflowStoreService,
        ViewerPreferenceStore,
    ],
) -> None:
    client, _, store, preferences = client_and_manager
    child_graph = _graph_with_output("inner")
    opened = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:root-a",
                "workflow_id": "root-a",
            },
            "parent_node_id": "child_1",
            "graph": child_graph,
        },
    )
    child = opened.json()
    workspace_id = ensure_workspace_identity(store.workspace_dir)
    environment_id = uuid4()
    preferences.set(
        SessionOutputPreferenceKey(
            workspace_id=workspace_id,
            session_id=child["session_id"],
            node_path=("inner",),
            output_key="image",
        ),
        environment_id,
        expected_revision=0,
    )
    endpoint = (
        f"/api/v1/nested-workflow-snapshots/{child['session_id']}"
        "/viewer-preferences/finalize-apply"
    )

    mismatch = await client.post(endpoint, json={"expected_revision": 0})
    assert mismatch.status_code == 409
    assert "has not accepted" in mismatch.json()["detail"]

    current = await client.get("/api/v1/workflow-drafts/root-a")
    accepted = await client.put(
        "/api/v1/workflow-drafts/root-a",
        json={
            "expected_revision": current.json()["draft_revision"],
            "graph": _parent_graph("child_1", child_graph),
        },
    )
    assert accepted.status_code == 200

    stale = await client.post(endpoint, json={"expected_revision": 1})
    assert stale.status_code == 409
    assert stale.json()["current_revision"] == 0

    finalized = await client.post(endpoint, json={"expected_revision": 0})
    assert finalized.status_code == 200
    favorite = finalized.json()["favorites"][0]
    assert favorite["environment_id"] == str(environment_id)
    assert favorite["key"] == {
        "kind": "persistent",
        "workspace_id": str(workspace_id),
        "workflow_id": "root-a",
        "identity_generation": store.workflow_generation("root-a"),
        "node_path": ["child_1", "inner"],
        "output_key": "image",
    }

    retry = await client.post(endpoint, json={"expected_revision": 0})
    assert retry.status_code == 200
    assert retry.json() == finalized.json()


async def test_finalize_nested_preferences_targets_parent_session(
    client_and_manager: tuple[
        httpx.AsyncClient,
        _ExecutionManager,
        WorkflowStoreService,
        ViewerPreferenceStore,
    ],
) -> None:
    client, _, store, preferences = client_and_manager
    child_graph = _graph_with_output("inner")
    parent_response = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:root-a",
                "workflow_id": "root-a",
            },
            "parent_node_id": "child_1",
            "graph": _parent_graph("child_2", child_graph),
        },
    )
    parent = parent_response.json()
    child_response = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {"kind": "nested", "session_id": parent["session_id"]},
            "parent_node_id": "child_2",
            "graph": child_graph,
        },
    )
    child = child_response.json()
    workspace_id = ensure_workspace_identity(store.workspace_dir)
    environment_id = uuid4()
    preferences.set(
        SessionOutputPreferenceKey(
            workspace_id=workspace_id,
            session_id=child["session_id"],
            node_path=("inner",),
            output_key="image",
        ),
        environment_id,
        expected_revision=0,
    )

    finalized = await client.post(
        f"/api/v1/nested-workflow-snapshots/{child['session_id']}"
        "/viewer-preferences/finalize-apply",
        json={"expected_revision": child["snapshot_revision"]},
    )

    assert finalized.status_code == 200
    key = finalized.json()["favorites"][0]["key"]
    assert key == {
        "kind": "session",
        "workspace_id": str(workspace_id),
        "session_id": parent["session_id"],
        "node_path": ["child_2", "inner"],
        "output_key": "image",
    }

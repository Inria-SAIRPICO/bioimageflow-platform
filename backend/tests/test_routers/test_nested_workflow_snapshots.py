"""Contract tests for private nested-workflow snapshot routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _ExecutionManager:
    def __init__(self) -> None:
        self.is_running = False


def _graph(
    node_id: str,
    published_name: str = "image",
    source_workflow_name: str | None = None,
) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": node_id,
                "name": node_id,
                "tool_name": "MissingTool",
                "position": [0, 0],
                "parameters": {},
                "source_workflow_name": source_workflow_name,
            }
        ],
        "edges": [],
        "published_inputs": [
            {
                "name": published_name,
                "internal_node_id": node_id,
                "internal_field": "image",
                "kind": "input",
                "schema": {"type": "Path"},
                "default": None,
            }
        ],
        "published_outputs": [],
    }


@pytest.fixture
async def client_and_manager(
    tmp_path: Path,
) -> AsyncIterator[tuple[httpx.AsyncClient, _ExecutionManager, WorkflowStoreService]]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    manager = _ExecutionManager()
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=manager,
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
        yield client, manager, store


async def test_open_replace_get_and_revision_checked_delete(
    client_and_manager: tuple[httpx.AsyncClient, _ExecutionManager, WorkflowStoreService],
) -> None:
    client, _, _ = client_and_manager
    opened = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:root-a",
                "workflow_id": "root-a",
            },
            "parent_node_id": "sub_1",
            "graph": _graph("inner", source_workflow_name="reusable-child"),
        },
    )
    assert opened.status_code == 201
    snapshot = opened.json()
    assert snapshot["graph"]["nodes"][0]["source_workflow_name"] == "reusable-child"

    replaced = await client.put(
        f"/api/v1/nested-workflow-snapshots/{snapshot['session_id']}",
        json={
            "expected_revision": snapshot["snapshot_revision"],
            "graph": _graph("inner", "renamed"),
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["snapshot_revision"] == 1
    assert replaced.json()["graph"]["published_inputs"][0]["name"] == "renamed"

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
    client_and_manager: tuple[httpx.AsyncClient, _ExecutionManager, WorkflowStoreService],
) -> None:
    client, manager, store = client_and_manager
    opened = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:root-a",
                "workflow_id": "root-a",
            },
            "parent_node_id": "sub_1",
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
            "parent_node_id": "sub_1",
            "graph": _graph("other"),
        },
    )

    assert [replace.status_code, delete.status_code, other_open.status_code] == [423, 423, 423]
    assert path.read_bytes() == before
    assert len(list(path.parent.glob("*.json"))) == 1

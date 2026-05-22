"""Tests for live workflow draft endpoints."""

from __future__ import annotations

import json
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
    def __init__(self, *, is_running: bool = False) -> None:
        self.is_running = is_running


async def _client(
    tmp_path: Path,
    *,
    is_running: bool = False,
) -> AsyncIterator[httpx.AsyncClient]:
    registry = ToolRegistryService()
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
            storage_path=tmp_path / "bif_data",
            disable_hot_reload=True,
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    async for ac in _client(tmp_path):
        yield ac


@pytest.fixture
async def locked_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    async for ac in _client(tmp_path, is_running=True):
        yield ac


async def _create_workflow(client: httpx.AsyncClient, name: str = "wf") -> None:
    response = await client.post(
        "/api/v1/workflows",
        json={"name": name, "display_name": name.split("/")[-1]},
    )
    assert response.status_code == 201


def _graph(node_id: str = "bad") -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": node_id,
                "name": "Bad",
                "tool_name": "MissingTool",
                "position": [1, 2],
                "parameters": {"value": 1},
            }
        ],
        "edges": [],
    }


async def test_get_synthesizes_draft_from_saved_workflow(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    await _create_workflow(client, "wf")

    response = await client.get("/api/v1/workflow-drafts/wf")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "wf"
    assert body["draft_revision"] == 0
    assert body["dirty_against_saved"] is False
    assert body["updated_by"] == "system"
    assert body["graph"] == {"nodes": [], "edges": [], "published_inputs": [], "published_outputs": []}
    assert body["base_saved_revision"].startswith("sha256:")
    assert not (
        tmp_path / "workspace" / "workflows" / "wf" / ".bioimageflow" / "draft.json"
    ).exists()

    agent_state = tmp_path / "workspace" / ".bioimageflow" / "agent-state.json"
    assert agent_state.exists()
    context = json.loads(agent_state.read_text())
    assert context["active_workflow_id"] == "wf"
    assert context["api_base_url"] == "http://test/api/v1"
    assert context["health_url"] == "http://test/api/v1/health"


async def test_put_writes_atomic_draft_and_conflicts_on_stale_revision(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    await _create_workflow(client, "wf")

    first = await client.put(
        "/api/v1/workflow-drafts/wf",
        json={
            "graph": _graph("n1"),
            "expected_revision": 0,
            "updated_by": "frontend",
        },
    )
    assert first.status_code == 200
    assert first.json()["draft_revision"] == 1
    assert first.json()["dirty_against_saved"] is True
    assert first.json()["validation"]["valid"] is False

    draft_path = tmp_path / "workspace" / "workflows" / "wf" / ".bioimageflow" / "draft.json"
    assert draft_path.exists()
    assert json.loads(draft_path.read_text())["graph"]["nodes"][0]["id"] == "n1"

    stale = await client.put(
        "/api/v1/workflow-drafts/wf",
        json={
            "graph": _graph("n2"),
            "expected_revision": 0,
            "updated_by": "frontend",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"] == "draft_revision_conflict"
    assert stale.json()["expected_revision"] == 0
    assert stale.json()["current_revision"] == 1


async def test_nested_workflow_draft_route_does_not_shadow_workflow_get(
    client: httpx.AsyncClient,
) -> None:
    await _create_workflow(client, "folder/wf")

    draft = await client.get("/api/v1/workflow-drafts/folder/wf")
    workflow = await client.get("/api/v1/workflows/folder/wf")

    assert draft.status_code == 200
    assert draft.json()["workflow_id"] == "folder/wf"
    assert workflow.status_code == 200
    assert workflow.json()["info"]["id"] == "folder/wf"


async def test_put_rejects_writes_while_execution_is_running(
    locked_client: httpx.AsyncClient,
) -> None:
    await _create_workflow(locked_client, "wf")

    response = await locked_client.put(
        "/api/v1/workflow-drafts/wf",
        json={
            "graph": {"nodes": [], "edges": []},
            "expected_revision": 0,
            "updated_by": "frontend",
        },
    )

    assert response.status_code == 423
    assert response.json()["error"] == "workflow_locked"

"""Tests for workflow CRUD endpoints."""

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
    def __init__(self, *, is_running: bool = False) -> None:
        self.is_running = is_running


async def _client(
    tmp_path: Path,
    *,
    is_running: bool = False,
) -> AsyncIterator[httpx.AsyncClient]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "outputs",
    )
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=_ExecutionManager(is_running=is_running),
            storage_path=tmp_path / "bif_data",
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


async def test_create_list_get_save_delete(client: httpx.AsyncClient) -> None:
    create = await client.post(
        "/api/v1/workflows",
        json={"name": "wf", "display_name": "Workflow"},
    )
    assert create.status_code == 201
    assert create.json()["name"] == "wf"
    assert create.json()["storage_path"] is not None

    listing = await client.get("/api/v1/workflows")
    assert listing.status_code == 200
    assert [item["name"] for item in listing.json()] == ["wf"]

    graph: dict[str, Any] = {
        "nodes": [
            {
                "id": "bad",
                "name": "Bad",
                "tool_name": "MissingTool",
                "position": [1, 2],
                "parameters": {"value": 1},
            }
        ],
        "edges": [],
    }
    save = await client.put("/api/v1/workflows/wf", json={"graph": graph})
    assert save.status_code == 200

    loaded = await client.get("/api/v1/workflows/wf")
    assert loaded.status_code == 200
    assert loaded.json()["info"]["name"] == "wf"
    assert loaded.json()["graph"]["nodes"][0]["id"] == "bad"
    assert loaded.json()["graph"]["nodes"][0]["tool_name"] == "MissingTool"
    assert loaded.json()["graph"]["nodes"][0]["position"] == [1.0, 2.0]
    assert loaded.json()["graph"]["nodes"][0]["parameters"] == {"value": 1}
    assert loaded.json()["missing_packages"] == []
    assert loaded.json()["missing_tools"] == []

    deleted = await client.delete("/api/v1/workflows/wf")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}


async def test_create_conflict_preserves_suggested_name(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.post("/api/v1/workflows", json={"name": "wf"})).status_code == 201
    conflict = await client.post("/api/v1/workflows", json={"name": "wf"})
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "conflict"
    assert conflict.json()["suggested_name"] == "wf_2"


async def test_patch_duplicate_conflict_preserves_suggested_name(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.post("/api/v1/workflows", json={"name": "wf"})).status_code == 201
    assert (await client.post("/api/v1/workflows", json={"name": "copy"})).status_code == 201

    conflict = await client.patch(
        "/api/v1/workflows/wf",
        json={"action": "duplicate", "new_name": "copy"},
    )

    assert conflict.status_code == 409
    assert conflict.json()["suggested_name"] == "copy_2"


async def test_patch_display_rename_conflict_suggests_canonical_name(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.post("/api/v1/workflows", json={"name": "wf"})).status_code == 201
    assert (
        await client.post("/api/v1/workflows", json={"name": "new_workflow"})
    ).status_code == 201

    conflict = await client.patch(
        "/api/v1/workflows/wf",
        json={"action": "update", "display_name": "New workflow"},
    )

    assert conflict.status_code == 409
    assert conflict.json()["suggested_name"] == "new_workflow_2"


async def test_patch_invalid_explicit_new_name_returns_400(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.post("/api/v1/workflows", json={"name": "wf"})).status_code == 201

    response = await client.patch(
        "/api/v1/workflows/wf",
        json={"action": "update", "new_name": "bad name"},
    )

    assert response.status_code == 400
    assert "Workflow name must start" in response.json()["detail"]


@pytest.mark.parametrize("method,path", [
    ("put", "/api/v1/workflows/wf"),
    ("patch", "/api/v1/workflows/wf"),
    ("delete", "/api/v1/workflows/wf"),
])
async def test_mutations_return_423_while_execution_running(
    locked_client: httpx.AsyncClient,
    method: str,
    path: str,
) -> None:
    assert (
        await locked_client.post("/api/v1/workflows", json={"name": "wf"})
    ).status_code == 201

    if method == "put":
        response = await locked_client.put(path, json={"graph": {"nodes": [], "edges": []}})
    elif method == "patch":
        response = await locked_client.patch(path, json={"action": "update", "display_name": "x"})
    else:
        response = await locked_client.delete(path)

    assert response.status_code == 423

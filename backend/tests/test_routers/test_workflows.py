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


class _FakeArchiveAdapter:
    def __init__(self, library: dict | None = None) -> None:
        self.library = library or {"nodes": [], "edges": []}
        self.export_calls: list[tuple[Path, Path]] = []
        self.import_payload: bytes | None = None
        self.extract_to: Path | None = None

    def export_archive(self, workflow_path: Path, archive_path: Path) -> None:
        self.export_calls.append((workflow_path, archive_path))
        archive_path.write_bytes(b"fake zip")

    def read_archive(self, archive_path: Path, *, extract_to: Path | None = None) -> dict:
        self.import_payload = archive_path.read_bytes()
        self.extract_to = extract_to
        if extract_to is not None:
            extract_to.mkdir(parents=True, exist_ok=True)
        return self.library


class _ConnectionManager:
    def __init__(self) -> None:
        self.workflow_tree_events: list[dict[str, str | None]] = []
        self.active_workflow_events: list[dict[str, str]] = []

    def publish_workflow_tree_changed(
        self,
        *,
        action: str,
        workflow_id: str | None = None,
    ) -> None:
        self.workflow_tree_events.append(
            {"action": action, "workflow_id": workflow_id}
        )

    def publish_active_workflow_changed(
        self,
        *,
        workflow_id: str,
        updated_by: str,
    ) -> None:
        self.active_workflow_events.append(
            {"workflow_id": workflow_id, "updated_by": updated_by}
        )


async def _client(
    tmp_path: Path,
    *,
    is_running: bool = False,
    archive_adapter: _FakeArchiveAdapter | None = None,
    connection_manager: _ConnectionManager | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "outputs",
        archive_adapter=archive_adapter,
    )
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=_ExecutionManager(is_running=is_running),
            storage_path=tmp_path / "bif_data",
            connection_manager=connection_manager,  # type: ignore[arg-type]
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


async def test_workflow_mutations_publish_tree_change_events(tmp_path: Path) -> None:
    connection_manager = _ConnectionManager()
    async for client in _client(tmp_path, connection_manager=connection_manager):
        create = await client.post(
            "/api/v1/workflows",
            json={"name": "wf", "display_name": "Workflow"},
        )
        assert create.status_code == 201

        patch = await client.patch(
            "/api/v1/workflows/wf",
            json={"action": "update", "display_name": "Renamed"},
        )
        assert patch.status_code == 200
        patched_id = patch.json()["id"]

        delete = await client.delete(f"/api/v1/workflows/{patched_id}")
        assert delete.status_code == 200

    assert connection_manager.workflow_tree_events == [
        {"action": "workflow_created", "workflow_id": "wf"},
        {"action": "workflow_updated", "workflow_id": patched_id},
        {"action": "workflow_deleted", "workflow_id": patched_id},
    ]


async def test_activate_workflow_publishes_active_workflow_event(tmp_path: Path) -> None:
    connection_manager = _ConnectionManager()
    async for client in _client(tmp_path, connection_manager=connection_manager):
        create = await client.post(
            "/api/v1/workflows",
            json={"name": "folder/wf", "display_name": "Workflow"},
        )
        assert create.status_code == 201

        response = await client.post("/api/v1/workflows/folder/wf/activate")
        assert response.status_code == 200

    assert connection_manager.active_workflow_events == [
        {"workflow_id": "folder/wf", "updated_by": "agent"}
    ]


async def test_export_workflow_download_response(tmp_path: Path) -> None:
    archive_adapter = _FakeArchiveAdapter()
    async for client in _client(tmp_path, archive_adapter=archive_adapter):
        assert (
            await client.post(
                "/api/v1/workflows",
                json={"name": "wf", "display_name": "Workflow"},
            )
        ).status_code == 201

        response = await client.post("/api/v1/workflows/wf/export")

    assert archive_adapter.export_calls[0][0] == tmp_path / "workflows" / "wf" / "workflow.json"
    assert archive_adapter.export_calls[0][1].name == "wf.bioimageflow.zip"
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert response.headers["content-disposition"] == 'attachment; filename="wf.bioimageflow.zip"'
    assert response.content == b"fake zip"


async def test_export_unknown_workflow_returns_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/v1/workflows/missing/export")

    assert response.status_code == 404


async def test_import_workflow_zip_upload_success(tmp_path: Path) -> None:
    archive_adapter = _FakeArchiveAdapter(
        library={
            "nodes": [
                {
                    "name": "n1",
                    "display_name": "Node",
                    "tool_class": "ExistingTool",
                    "constants": {"threshold": 3},
                }
            ],
            "edges": [],
        }
    )
    async for client in _client(tmp_path, archive_adapter=archive_adapter):
        response = await client.post(
            "/api/v1/workflows/import",
            files={
                "file": (
                    "imported.bioimageflow.zip",
                    b"fake zip",
                    "application/zip",
                )
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["info"]["name"] == "imported"
    assert archive_adapter.import_payload == b"fake zip"
    assert archive_adapter.extract_to == tmp_path / "workflows" / "imported"


async def test_import_workflow_rejects_json_upload(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/workflows/import",
        files={"file": ("imported.bioimageflow.json", b"{}", "application/json")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Workflow imports must be .bioimageflow.zip archives"


async def test_import_workflow_archive_conflict_and_name_override(
    tmp_path: Path,
) -> None:
    archive_adapter = _FakeArchiveAdapter()
    async for client in _client(tmp_path, archive_adapter=archive_adapter):
        assert (await client.post("/api/v1/workflows", json={"name": "wf"})).status_code == 201
        conflict = await client.post(
            "/api/v1/workflows/import",
            files={"file": ("wf.bioimageflow.zip", b"fake zip", "application/zip")},
        )

        assert conflict.status_code == 409
        assert conflict.json()["suggested_name"] == "wf_2"

        renamed = await client.post(
            "/api/v1/workflows/import",
            data={"name_override": "wf_2"},
            files={"file": ("wf.bioimageflow.zip", b"fake zip", "application/zip")},
        )

    assert renamed.status_code == 201
    assert renamed.json()["info"]["name"] == "wf_2"


async def test_import_workflow_invalid_archive_payload(
    client: httpx.AsyncClient,
) -> None:
    invalid = await client.post(
        "/api/v1/workflows/import",
        files={"file": ("bad.bioimageflow.zip", b"not a zip", "application/zip")},
    )
    assert invalid.status_code == 422


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
        json={"action": "update", "new_name": "bad name!"},
    )

    assert response.status_code == 400
    assert "Workflow name must start" in response.json()["detail"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("put", "/api/v1/workflows/wf"),
        ("patch", "/api/v1/workflows/wf"),
        ("delete", "/api/v1/workflows/wf"),
    ],
)
async def test_mutations_return_423_while_execution_running(
    locked_client: httpx.AsyncClient,
    method: str,
    path: str,
) -> None:
    assert (await locked_client.post("/api/v1/workflows", json={"name": "wf"})).status_code == 201

    if method == "put":
        response = await locked_client.put(path, json={"graph": {"nodes": [], "edges": []}})
    elif method == "patch":
        response = await locked_client.patch(path, json={"action": "update", "display_name": "x"})
    else:
        response = await locked_client.delete(path)

    assert response.status_code == 423


async def test_import_returns_423_while_execution_running(
    locked_client: httpx.AsyncClient,
) -> None:
    response = await locked_client.post(
        "/api/v1/workflows/import",
        files={"file": ("imported.bioimageflow.zip", b"fake zip", "application/zip")},
    )

    assert response.status_code == 423

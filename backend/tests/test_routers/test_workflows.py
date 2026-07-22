"""Tests for workflow CRUD endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from unittest.mock import MagicMock

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services import workflow_store as workflow_store_module
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
    RootWorkflowSnapshotMove,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from tests.graph_factory import graph_document

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _ExecutionManager:
    def __init__(self, *, is_running: bool = False) -> None:
        self.is_running = is_running


class _FakeArchiveAdapter:
    def __init__(self, library: dict | None = None) -> None:
        self.library = library or _library_graph()
        self.export_calls: list[tuple[dict[str, Any], Path]] = []
        self.import_payload: bytes | None = None
        self.extract_to: Path | None = None

    def export_archive(self, workflow: dict[str, Any], archive_path: Path) -> None:
        self.export_calls.append((workflow, archive_path))
        archive_path.write_bytes(b"fake zip")

    def read_archive(self, archive_path: Path, *, extract_to: Path | None = None) -> dict:
        self.import_payload = archive_path.read_bytes()
        self.extract_to = extract_to
        if extract_to is not None:
            extract_to.mkdir(parents=True, exist_ok=True)
        return self.library


def _library_graph(*, nodes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "imported",
        "display_name": "Imported",
        "interface": {"inputs": [], "outputs": []},
        "nodes": nodes or [],
        "edges": [],
        "config": {"storage_path": "./bif_data", "engine": "direct", "execution": "parallel"},
    }


class _ConnectionManager:
    def __init__(self) -> None:
        self.workflow_tree_events: list[dict[str, str | int | None]] = []
        self.active_workflow_events: list[dict[str, str]] = []

    def publish_workflow_tree_changed(
        self,
        *,
        action: str,
        workflow_id: str | None = None,
        identity_generation: int | None = None,
    ) -> None:
        self.workflow_tree_events.append(
            {
                "action": action,
                "workflow_id": workflow_id,
                "identity_generation": identity_generation,
            }
        )

    def publish_active_workflow_changed(
        self,
        *,
        workflow_id: str,
        updated_by: str,
    ) -> None:
        self.active_workflow_events.append({"workflow_id": workflow_id, "updated_by": updated_by})


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
    assert create.json()["identity_generation"] == 1

    listing = await client.get("/api/v1/workflows")
    assert listing.status_code == 200
    assert [item["name"] for item in listing.json()] == ["wf"]
    assert listing.json()[0]["identity_generation"] == 1

    graph = graph_document(
        name="wf",
        display_name="Workflow",
        nodes=[
            {
                "type": "tool",
                "id": "bad",
                "name": "Bad",
                "tool_name": "MissingTool",
                "position": [1, 2],
                "parameters": {"value": 1},
            }
        ],
    )
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
    assert [item["node_id"] for item in loaded.json()["missing_tools"]] == ["bad"]

    deleted = await client.delete("/api/v1/workflows/wf")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "identity_generation": 2}


async def test_reveal_latest_outputs_opens_the_workflow_projection(
    client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reveal = MagicMock()
    monkeypatch.setattr(
        "bioimageflow_server.routers.workflows.reveal_in_file_browser",
        reveal,
    )
    created = await client.post("/api/v1/workflows", json={"name": "folder/wf"})
    assert created.status_code == 201

    response = await client.post(
        "/api/v1/workflows/folder/wf/outputs/latest/reveal"
    )

    assert response.status_code == 200, response.text
    expected = tmp_path / "outputs" / "folder" / "wf" / "outputs" / "latest"
    assert response.json()["path"] == str(expected)
    assert expected.is_dir()
    reveal.assert_called_once_with(str(expected))


async def test_format_status_reports_hidden_invalid_workflows(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    invalid = tmp_path / "workflows" / "broken" / "workflow.json"
    invalid.parent.mkdir(parents=True)
    invalid.write_text('{"not": "a workflow"}', encoding="utf-8")

    response = await client.get("/api/v1/workflows/format-status")

    assert response.status_code == 200
    assert response.json()["notices"][0]["workflow_id"] == "broken"
    assert response.json()["notices"][0]["status"] == "error"


async def test_empty_folder_promotion_needs_no_move_journal(
    client: httpx.AsyncClient,
) -> None:
    created = await client.post(
        "/api/v1/workflows/folders",
        json={"path": "empty"},
    )
    assert created.status_code == 201

    deleted = await client.request(
        "DELETE",
        "/api/v1/workflows/folders/empty",
        json={"policy": "move_children_up"},
    )

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    tree = await client.get("/api/v1/workflows/tree")
    assert all(folder["path"] != "empty" for folder in tree.json()["folders"])


async def test_delete_workflow_removes_its_retained_nested_snapshot_tree(
    client: httpx.AsyncClient,
) -> None:
    created = await client.post(
        "/api/v1/workflows",
        json={"name": "wf", "display_name": "Workflow"},
    )
    assert created.status_code == 201
    parent = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "root",
                "canvas_id": "workflow:wf",
                "workflow_id": "wf",
            },
            "parent_node_id": "child_1",
            "graph": graph_document(name="child", display_name="Child"),
        },
    )
    assert parent.status_code == 201
    child = await client.post(
        "/api/v1/nested-workflow-snapshots/open",
        json={
            "owner": {
                "kind": "nested",
                "session_id": parent.json()["session_id"],
            },
            "parent_node_id": "child_2",
            "graph": graph_document(name="grandchild", display_name="Grandchild"),
        },
    )
    assert child.status_code == 201

    deleted = await client.delete("/api/v1/workflows/wf")

    assert deleted.status_code == 200
    for session_id in (parent.json()["session_id"], child.json()["session_id"]):
        response = await client.get(f"/api/v1/nested-workflow-snapshots/{session_id}")
        assert response.status_code == 404


async def test_delete_folder_children_removes_each_retained_snapshot_tree(
    client: httpx.AsyncClient,
) -> None:
    session_ids: list[str] = []
    for workflow_id in ("project/a", "project/sub/b"):
        created = await client.post(
            "/api/v1/workflows",
            json={"name": workflow_id, "display_name": workflow_id.split("/")[-1]},
        )
        assert created.status_code == 201
        opened = await client.post(
            "/api/v1/nested-workflow-snapshots/open",
            json={
                "owner": {
                    "kind": "root",
                    "canvas_id": f"workflow:{workflow_id}",
                    "workflow_id": workflow_id,
                },
                "parent_node_id": "child_1",
                "graph": graph_document(name="child", display_name="Child"),
            },
        )
        assert opened.status_code == 201
        session_ids.append(opened.json()["session_id"])

    deleted = await client.request(
        "DELETE",
        "/api/v1/workflows/folders/project",
        json={"policy": "delete_children"},
    )

    assert deleted.status_code == 200
    for session_id in session_ids:
        response = await client.get(f"/api/v1/nested-workflow-snapshots/{session_id}")
        assert response.status_code == 404


async def test_direct_workflow_move_rewrites_snapshot_generation_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    move_calls: list[list[RootWorkflowSnapshotMove]] = []
    original_move = NestedWorkflowSnapshotService.move_root_workflows

    def observed_move(
        service: NestedWorkflowSnapshotService,
        moves: list[RootWorkflowSnapshotMove],
    ) -> list[Any]:
        move_calls.append(moves)
        return original_move(service, moves)

    monkeypatch.setattr(NestedWorkflowSnapshotService, "move_root_workflows", observed_move)
    async for client in _client(tmp_path):
        created = await client.post("/api/v1/workflows", json={"name": "project/wf"})
        moved = await client.patch(
            "/api/v1/workflows/project/wf",
            json={"action": "update", "new_id": "archive/wf"},
        )

    assert moved.status_code == 200
    assert move_calls == [
        [
            RootWorkflowSnapshotMove(
                old_workflow_id="project/wf",
                old_identity_generation=created.json()["identity_generation"],
                new_workflow_id="archive/wf",
                new_identity_generation=moved.json()["identity_generation"],
            )
        ]
    ]


async def test_folder_rename_rewrites_each_snapshot_generation_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    move_calls: list[list[RootWorkflowSnapshotMove]] = []
    original_move = NestedWorkflowSnapshotService.move_root_workflows

    def observed_move(
        service: NestedWorkflowSnapshotService,
        moves: list[RootWorkflowSnapshotMove],
    ) -> list[Any]:
        move_calls.append(moves)
        return original_move(service, moves)

    monkeypatch.setattr(NestedWorkflowSnapshotService, "move_root_workflows", observed_move)
    async for client in _client(tmp_path):
        first = await client.post("/api/v1/workflows", json={"name": "project/a"})
        second = await client.post("/api/v1/workflows", json={"name": "project/nested/b"})
        renamed = await client.patch(
            "/api/v1/workflows/folders/project",
            json={"new_path": "archive"},
        )
        moved_first = await client.get("/api/v1/workflows/archive/a")
        moved_second = await client.get("/api/v1/workflows/archive/nested/b")

    assert renamed.status_code == 200
    assert move_calls == [
        [
            RootWorkflowSnapshotMove(
                old_workflow_id="project/a",
                old_identity_generation=first.json()["identity_generation"],
                new_workflow_id="archive/a",
                new_identity_generation=moved_first.json()["info"]["identity_generation"],
            ),
            RootWorkflowSnapshotMove(
                old_workflow_id="project/nested/b",
                old_identity_generation=second.json()["identity_generation"],
                new_workflow_id="archive/nested/b",
                new_identity_generation=moved_second.json()["info"]["identity_generation"],
            ),
        ]
    ]


async def test_folder_promotion_rewrites_each_snapshot_generation_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    move_calls: list[list[RootWorkflowSnapshotMove]] = []
    original_move = NestedWorkflowSnapshotService.move_root_workflows

    def observed_move(
        service: NestedWorkflowSnapshotService,
        moves: list[RootWorkflowSnapshotMove],
    ) -> list[Any]:
        move_calls.append(moves)
        return original_move(service, moves)

    monkeypatch.setattr(NestedWorkflowSnapshotService, "move_root_workflows", observed_move)
    async for client in _client(tmp_path):
        first = await client.post("/api/v1/workflows", json={"name": "project/a"})
        second = await client.post("/api/v1/workflows", json={"name": "project/nested/b"})
        deleted = await client.request(
            "DELETE",
            "/api/v1/workflows/folders/project",
            json={"policy": "move_children_up"},
        )
        moved_first = await client.get("/api/v1/workflows/a")
        moved_second = await client.get("/api/v1/workflows/nested/b")

    assert deleted.status_code == 200
    assert move_calls == [
        [
            RootWorkflowSnapshotMove(
                old_workflow_id="project/a",
                old_identity_generation=first.json()["identity_generation"],
                new_workflow_id="a",
                new_identity_generation=moved_first.json()["info"]["identity_generation"],
            ),
            RootWorkflowSnapshotMove(
                old_workflow_id="project/nested/b",
                old_identity_generation=second.json()["identity_generation"],
                new_workflow_id="nested/b",
                new_identity_generation=moved_second.json()["info"]["identity_generation"],
            ),
        ]
    ]


async def test_non_identity_workflow_updates_do_not_move_snapshots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    move_calls: list[list[RootWorkflowSnapshotMove]] = []

    def observed_move(
        _service: NestedWorkflowSnapshotService,
        moves: list[RootWorkflowSnapshotMove],
    ) -> list[Any]:
        move_calls.append(moves)
        return []

    monkeypatch.setattr(NestedWorkflowSnapshotService, "move_root_workflows", observed_move)
    async for client in _client(tmp_path):
        assert (await client.post("/api/v1/workflows", json={"name": "source"})).status_code == 201
        display = await client.patch(
            "/api/v1/workflows/source",
            json={"action": "update", "display_name": "Renamed"},
        )
        duplicate = await client.patch(
            "/api/v1/workflows/source",
            json={"action": "duplicate", "new_name": "copy"},
        )

    assert display.status_code == 200
    assert duplicate.status_code == 200
    assert move_calls == []


async def test_workflow_move_holds_snapshot_then_structure_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_depth = 0
    structure_depth = 0
    preflight_complete = False
    original_snapshot_mutation = NestedWorkflowSnapshotService.snapshot_mutation
    original_preflight = NestedWorkflowSnapshotService.preflight_root_workflow_moves
    original_structure_mutation = WorkflowStoreService.workflow_structure_mutation
    original_patch = WorkflowStoreService.patch_workflow

    @contextmanager
    def observed_snapshot_mutation(service: NestedWorkflowSnapshotService):
        nonlocal snapshot_depth
        with original_snapshot_mutation(service):
            snapshot_depth += 1
            try:
                yield
            finally:
                snapshot_depth -= 1

    @contextmanager
    def observed_structure_mutation(store: WorkflowStoreService):
        nonlocal structure_depth
        with original_structure_mutation(store):
            structure_depth += 1
            try:
                yield
            finally:
                structure_depth -= 1

    def observed_patch(
        store: WorkflowStoreService,
        name: str,
        body: Any,
        *,
        move_operation_id: Any = None,
    ) -> Any:
        assert snapshot_depth > 0
        assert structure_depth > 0
        assert preflight_complete is True
        return original_patch(
            store,
            name,
            body,
            move_operation_id=move_operation_id,
        )

    def observed_preflight(service: NestedWorkflowSnapshotService) -> None:
        nonlocal preflight_complete
        assert snapshot_depth > 0
        assert structure_depth > 0
        original_preflight(service)
        preflight_complete = True

    def observed_move(
        _service: NestedWorkflowSnapshotService,
        _moves: list[RootWorkflowSnapshotMove],
    ) -> list[Any]:
        assert snapshot_depth > 0
        assert structure_depth > 0
        return []

    async for client in _client(tmp_path):
        assert (await client.post("/api/v1/workflows", json={"name": "old"})).status_code == 201
        monkeypatch.setattr(
            NestedWorkflowSnapshotService,
            "snapshot_mutation",
            observed_snapshot_mutation,
        )
        monkeypatch.setattr(
            WorkflowStoreService,
            "workflow_structure_mutation",
            observed_structure_mutation,
        )
        monkeypatch.setattr(WorkflowStoreService, "patch_workflow", observed_patch)
        monkeypatch.setattr(
            NestedWorkflowSnapshotService,
            "preflight_root_workflow_moves",
            observed_preflight,
        )
        monkeypatch.setattr(NestedWorkflowSnapshotService, "move_root_workflows", observed_move)

        moved = await client.patch(
            "/api/v1/workflows/old",
            json={"action": "update", "new_id": "new"},
        )

    assert moved.status_code == 200
    assert snapshot_depth == 0
    assert structure_depth == 0


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

        recreate = await client.post(
            "/api/v1/workflows",
            json={"name": patched_id, "display_name": "Recreated"},
        )
        assert recreate.status_code == 201

    assert connection_manager.workflow_tree_events == [
        {
            "action": "workflow_created",
            "workflow_id": "wf",
            "identity_generation": 1,
        },
        {
            "action": "workflow_updated",
            "workflow_id": patched_id,
            "identity_generation": 1,
        },
        {
            "action": "workflow_deleted",
            "workflow_id": patched_id,
            "identity_generation": 2,
        },
        {
            "action": "workflow_created",
            "workflow_id": patched_id,
            "identity_generation": 3,
        },
    ]


async def test_committed_move_ignores_tree_change_publish_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection_manager = _ConnectionManager()
    original_publish = connection_manager.publish_workflow_tree_changed

    def fail_update_publish(
        *,
        action: str,
        workflow_id: str | None = None,
        identity_generation: int | None = None,
    ) -> None:
        if action == "workflow_updated":
            raise OSError("notification transport unavailable")
        original_publish(
            action=action,
            workflow_id=workflow_id,
            identity_generation=identity_generation,
        )

    monkeypatch.setattr(connection_manager, "publish_workflow_tree_changed", fail_update_publish)
    async for client in _client(tmp_path, connection_manager=connection_manager):
        assert (await client.post("/api/v1/workflows", json={"name": "old"})).status_code == 201
        with caplog.at_level("ERROR", logger="bioimageflow_server.routers.workflows"):
            moved = await client.patch(
                "/api/v1/workflows/old",
                json={"action": "update", "new_id": "new"},
            )

    assert moved.status_code == 200
    assert (tmp_path / "workflows" / "new" / "workflow.json").exists()
    assert not (tmp_path / ".bioimageflow" / "workflow-move-journal.json").exists()
    assert "committed but could not be published" in caplog.text


async def test_interrupted_move_returns_recovery_required_and_keeps_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_snapshot_move(
        _service: NestedWorkflowSnapshotService,
        _moves: list[RootWorkflowSnapshotMove],
    ) -> list[Any]:
        raise OSError("snapshot storage unavailable")

    monkeypatch.setattr(NestedWorkflowSnapshotService, "move_root_workflows", fail_snapshot_move)
    async for client in _client(tmp_path):
        assert (await client.post("/api/v1/workflows", json={"name": "old"})).status_code == 201
        interrupted = await client.patch(
            "/api/v1/workflows/old",
            json={"action": "update", "new_id": "new"},
        )
        blocked = await client.patch(
            "/api/v1/workflows/new",
            json={"action": "update", "new_id": "later"},
        )
        blocked_save = await client.put(
            "/api/v1/workflows/new",
            json={"graph": graph_document()},
        )
        blocked_delete = await client.delete("/api/v1/workflows/new")
        blocked_create = await client.post(
            "/api/v1/workflows",
            json={"name": "other"},
        )
        blocked_tool_create = await client.post(
            "/api/v1/tools",
            params={"workflow_name": "old"},
            json={"name": "UnsafeTool", "tool_type": "ProcessingTool"},
        )
        blocked_draft = await client.put(
            "/api/v1/workflow-drafts/new",
            json={
                "graph": graph_document(),
                "expected_revision": 0,
                "updated_by": "frontend",
            },
        )
        blocked_run = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": graph_document(),
                "workflow_name": "new",
                "draft_revision": 0,
            },
        )

    assert interrupted.status_code == 503
    assert interrupted.json()["error"] == "workflow_move_recovery_required"
    assert blocked.status_code == 503
    assert blocked.json()["error"] == "workflow_move_recovery_required"
    for response in (
        blocked_save,
        blocked_delete,
        blocked_create,
        blocked_tool_create,
        blocked_draft,
        blocked_run,
    ):
        assert response.status_code == 503
        assert response.json()["error"] == "workflow_move_recovery_required"
    assert (tmp_path / "workflows" / "new" / "workflow.json").exists()
    assert not (tmp_path / "workflows" / "later").exists()
    assert not (tmp_path / "workflows" / "other").exists()
    assert not (tmp_path / "workflows" / "old").exists()
    assert (tmp_path / ".bioimageflow" / "workflow-move-journal.json").exists()


async def test_delete_rejects_stale_expected_identity_generation_without_event(
    tmp_path: Path,
) -> None:
    connection_manager = _ConnectionManager()
    async for client in _client(tmp_path, connection_manager=connection_manager):
        create = await client.post("/api/v1/workflows", json={"name": "wf"})
        assert create.status_code == 201
        generation = create.json()["identity_generation"]

        stale = await client.delete(
            "/api/v1/workflows/wf",
            params={"expected_identity_generation": generation - 1},
        )
        assert stale.status_code == 409
        assert stale.json() == {
            "error": "workflow_identity_generation_conflict",
            "detail": f"Workflow 'wf' generation is {generation}, not expected {generation - 1}",
            "field": None,
        }
        assert (await client.get("/api/v1/workflows/wf")).status_code == 200
        assert connection_manager.workflow_tree_events == [
            {
                "action": "workflow_created",
                "workflow_id": "wf",
                "identity_generation": generation,
            }
        ]

        deleted = await client.delete(
            "/api/v1/workflows/wf",
            params={"expected_identity_generation": generation},
        )
        assert deleted.status_code == 200
        assert deleted.json()["identity_generation"] > generation


async def test_committed_delete_ignores_managed_output_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection_manager = _ConnectionManager()
    original_rmtree = workflow_store_module.shutil.rmtree
    async for client in _client(tmp_path, connection_manager=connection_manager):
        create = await client.post("/api/v1/workflows", json={"name": "wf"})
        assert create.status_code == 201
        managed_path = Path(create.json()["storage_path"])
        managed_path.mkdir(parents=True)

        def fail_managed_cleanup(path: str | Path, *args: Any, **kwargs: Any) -> None:
            if Path(path) == managed_path:
                raise OSError("managed cleanup failed")
            original_rmtree(path, *args, **kwargs)

        monkeypatch.setattr(workflow_store_module.shutil, "rmtree", fail_managed_cleanup)
        with caplog.at_level(
            "ERROR",
            logger="bioimageflow_server.services.workflow_store",
        ):
            deleted = await client.delete("/api/v1/workflows/wf")

        assert deleted.status_code == 200
        assert (await client.get("/api/v1/workflows/wf")).status_code == 404
        assert managed_path.exists()

    assert connection_manager.workflow_tree_events[-1] == {
        "action": "workflow_deleted",
        "workflow_id": "wf",
        "identity_generation": 2,
    }
    assert "managed output cleanup failed" in caplog.text


async def test_committed_delete_ignores_nested_snapshot_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection_manager = _ConnectionManager()

    def fail_snapshot_cleanup(
        _service: NestedWorkflowSnapshotService,
        _workflow_id: str,
    ) -> list[Any]:
        raise OSError("snapshot cleanup failed")

    monkeypatch.setattr(
        NestedWorkflowSnapshotService,
        "delete_for_root_workflow",
        fail_snapshot_cleanup,
    )
    async for client in _client(tmp_path, connection_manager=connection_manager):
        create = await client.post("/api/v1/workflows", json={"name": "wf"})
        assert create.status_code == 201

        with caplog.at_level(
            "ERROR",
            logger="bioimageflow_server.routers.workflows",
        ):
            deleted = await client.delete("/api/v1/workflows/wf")

        assert deleted.status_code == 200
        assert (await client.get("/api/v1/workflows/wf")).status_code == 404

    assert connection_manager.workflow_tree_events[-1] == {
        "action": "workflow_deleted",
        "workflow_id": "wf",
        "identity_generation": 2,
    }
    assert "retained nested snapshot cleanup failed" in caplog.text


async def test_committed_folder_delete_ignores_nested_snapshot_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection_manager = _ConnectionManager()

    def fail_snapshot_cleanup(
        _service: NestedWorkflowSnapshotService,
        _workflow_ids: list[str],
    ) -> list[Any]:
        raise OSError("folder snapshot cleanup failed")

    monkeypatch.setattr(
        NestedWorkflowSnapshotService,
        "delete_for_root_workflows",
        fail_snapshot_cleanup,
    )
    async for client in _client(tmp_path, connection_manager=connection_manager):
        create = await client.post(
            "/api/v1/workflows",
            json={"name": "project/wf"},
        )
        assert create.status_code == 201

        with caplog.at_level(
            "ERROR",
            logger="bioimageflow_server.routers.workflows",
        ):
            deleted = await client.request(
                "DELETE",
                "/api/v1/workflows/folders/project",
                json={"policy": "delete_children"},
            )

        assert deleted.status_code == 200
        assert (await client.get("/api/v1/workflows/project/wf")).status_code == 404

    assert connection_manager.workflow_tree_events[-1] == {
        "action": "folder_deleted",
        "workflow_id": None,
        "identity_generation": None,
    }
    assert "retained nested snapshot cleanup failed" in caplog.text


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

    assert archive_adapter.export_calls[0][0]["name"] == "wf"
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
        library=_library_graph(
            nodes=[
                {
                    "type": "tool",
                    "name": "n1",
                    "tool_module": "missing_module",
                    "tool_class": "ExistingTool",
                    "tool_package": None,
                    "tool_package_version": None,
                    "constants": {"threshold": {"__type__": "int", "value": 3}},
                }
            ]
        )
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
    assert archive_adapter.extract_to is None


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


async def test_patch_display_name_keeps_identity_when_canonical_slug_exists(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.post("/api/v1/workflows", json={"name": "wf"})).status_code == 201
    assert (
        await client.post("/api/v1/workflows", json={"name": "new_workflow"})
    ).status_code == 201

    response = await client.patch(
        "/api/v1/workflows/wf",
        json={"action": "update", "display_name": "New workflow"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "wf"
    assert response.json()["display_name"] == "New workflow"


async def test_patch_explicit_rename_conflict_suggests_alternative(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.post("/api/v1/workflows", json={"name": "wf"})).status_code == 201
    assert (
        await client.post("/api/v1/workflows", json={"name": "new_workflow"})
    ).status_code == 201

    conflict = await client.patch(
        "/api/v1/workflows/wf",
        json={"action": "update", "new_name": "new_workflow"},
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
        response = await locked_client.put(path, json={"graph": graph_document()})
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

"""Editor source identity agrees with the accepted node's execution identity."""

from pathlib import Path

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.workflow_artifacts import OwnedWorkflowSources
from tests.test_routers.test_editor import _EditorStub
from tests.test_services.test_editable_workflow_sources import SOURCE, imported_store, run

pytestmark = pytest.mark.anyio


async def test_open_node_targets_imported_source_and_saved_edit_executes(tmp_path: Path):
    store = imported_store(tmp_path)
    unrelated = tmp_path / "qa_increment.py"
    unrelated.write_text(SOURCE.replace("n + 1", "n + 100"))
    store.tool_registry.register_custom_tool_file(unrelated, "QaIncrement")
    editor = _EditorStub()
    app = create_app(
        config=AppConfig(
            workspace_path=tmp_path,
            workflow_root=store.root_dir,
            workflow_store=store,
            tool_registry=store.tool_registry,
            editor_service=editor,
            disable_hot_reload=True,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        draft = (await client.get("/api/v1/workflow-drafts/reference")).json()
        response = await client.post(
            "/api/v1/editor/open-node",
            json={
                "workflow_id": "reference",
                "identity_generation": store.workflow_generation("reference"),
                "node_id": "increment",
                "expected_revision": draft["draft_revision"],
            },
        )
        assert response.status_code == 200, response.text
        path = Path(response.json()["path"])
        assert path == OwnedWorkflowSources(store.workflow_dir("reference")).source_path(
            "increment"
        )
        path.write_text(SOURCE.replace("n + 1", "n + 20"))
        assert run(store) == [21, 22, 23]
        assert "n + 100" in unrelated.read_text()


async def test_nested_script_edit_forks_only_the_private_snapshot(tmp_path: Path):
    store = imported_store(tmp_path)
    app = create_app(
        config=AppConfig(
            workspace_path=tmp_path,
            workflow_root=store.root_dir,
            workflow_store=store,
            tool_registry=store.tool_registry,
            editor_service=_EditorStub(),
            disable_hot_reload=True,
        )
    )
    generation = store.workflow_generation("reference")
    graph = store.get_workflow("reference").graph
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        opened = await client.post(
            "/api/v1/nested-workflow-snapshots/open",
            json={
                "owner": {
                    "kind": "root",
                    "canvas_id": "workflow:reference",
                    "workflow_id": "reference",
                    "identity_generation": generation,
                },
                "parent_node_id": "child",
                "graph": graph.model_dump(mode="json"),
            },
        )
        assert opened.status_code == 201, opened.text
        snapshot = opened.json()
        response = await client.post(
            "/api/v1/editor/open-node",
            json={
                "workflow_id": "reference",
                "identity_generation": generation,
                "node_id": "increment",
                "session_id": snapshot["session_id"],
                "expected_revision": snapshot["snapshot_revision"],
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        path = Path(result["path"])
        assert path != OwnedWorkflowSources(store.workflow_dir("reference")).source_path(
            "increment"
        )
        path.write_text(SOURCE.replace("n + 1", "n + 20"))
        from bioimageflow_server.models.graph import GraphState

        assert run(store, graph=GraphState.model_validate(result["snapshot"]["graph"])) == [
            21,
            22,
            23,
        ]
        assert run(store) == [2, 3, 4]
        repeated = await client.post(
            "/api/v1/editor/open-node",
            json={
                "workflow_id": "reference",
                "identity_generation": generation,
                "node_id": "increment",
                "session_id": snapshot["session_id"],
                "expected_revision": result["snapshot"]["snapshot_revision"],
            },
        )
        assert repeated.status_code == 200
        assert repeated.json()["path"] == str(path)


@pytest.mark.parametrize(
    "change", [{"identity_generation": 999}, {"expected_revision": 999}, {"node_id": "absent"}]
)
async def test_open_node_rejects_stale_or_missing_identity(tmp_path: Path, change: dict):
    store = imported_store(tmp_path)
    editor = _EditorStub()
    app = create_app(
        config=AppConfig(
            workspace_path=tmp_path,
            workflow_root=store.root_dir,
            workflow_store=store,
            tool_registry=store.tool_registry,
            editor_service=editor,
            disable_hot_reload=True,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        draft = (await client.get("/api/v1/workflow-drafts/reference")).json()
        response = await client.post(
            "/api/v1/editor/open-node",
            json={
                "workflow_id": "reference",
                "identity_generation": store.workflow_generation("reference"),
                "node_id": "increment",
                "expected_revision": draft["draft_revision"],
                **change,
            },
        )
        assert response.status_code in (404, 409), response.text
        assert editor.paths == []

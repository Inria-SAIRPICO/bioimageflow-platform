from __future__ import annotations

import json

import pytest

from bioimageflow_server.models.nested_workflow_snapshot import NestedSnapshotOwner
from bioimageflow_server.models.workflow import WorkflowCreate
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import (
    WorkflowMoveRecoveryError,
    WorkflowStoreService,
)


def _store(tmp_path) -> WorkflowStoreService:
    return WorkflowStoreService(tmp_path / "workspace/workflows", ToolRegistryService())


def _downgrade(graph: dict) -> dict:
    graph = json.loads(json.dumps(graph))
    graph["schema_version"] = 1
    for node in graph["nodes"]:
        node.pop("viewer_additions", None)
        if node["type"] == "workflow":
            node["workflow"] = _downgrade(node["workflow"])
    for output in graph["interface"]["outputs"]:
        output.pop("viewer_addition", None)
        if isinstance(output.get("schema"), dict):
            output["schema"].pop("viewer", None)
    return graph


def _write_draft(store, workflow_id, graph, base, *, dirty) -> None:
    path = store.workflow_dir(workflow_id) / ".bioimageflow/draft.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "draft_version": 1,
                "workflow_id": workflow_id,
                "base_saved_revision": base,
                "draft_revision": 4,
                "updated_at": "2026-09-15T10:00:00Z",
                "updated_by": "frontend",
                "dirty_against_saved": dirty,
                "graph": graph,
                "validation": {"valid": True, "node_statuses": {}, "errors": []},
            }
        )
    )


def test_migrates_recursive_saved_clean_dirty_and_nested_snapshot_truth(tmp_path) -> None:
    store = _store(tmp_path)
    for workflow_id in ("clean", "dirty"):
        store.create_workflow(WorkflowCreate(name=workflow_id))
        path = store.workflow_dir(workflow_id) / "workflow.json"
        raw = json.loads(path.read_text())
        raw["graph"] = _downgrade(raw["graph"])
        raw["artifact_hash"] = "sha256:" + ("1" if workflow_id == "clean" else "2") * 64
        path.write_text(json.dumps(raw))
        draft_graph = json.loads(json.dumps(raw["graph"]))
        if workflow_id == "dirty":
            draft_graph["display_name"] = "Actually changed"
        _write_draft(
            store,
            workflow_id,
            draft_graph,
            raw["artifact_hash"],
            dirty=workflow_id == "dirty",
        )

    snapshots = NestedWorkflowSnapshotService(lambda: store)
    opened = snapshots.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="workflow:clean",
            workflow_id="clean",
            identity_generation=store.workflow_generation("clean"),
        ),
        "child",
        store.get_workflow("clean").graph,
    )
    snapshot_path = (
        store.workspace_dir
        / ".bioimageflow/nested-workflow-snapshots"
        / f"{opened.session_id}.json"
    )
    raw_snapshot = json.loads(snapshot_path.read_text())
    raw_snapshot["graph"] = _downgrade(raw_snapshot["graph"])
    snapshot_path.write_text(json.dumps(raw_snapshot))

    store.migrate_schema_v2_workflows()

    for workflow_id, expected_dirty in (("clean", False), ("dirty", True)):
        document = json.loads(
            (store.workflow_dir(workflow_id) / "workflow.json").read_text()
        )
        draft = json.loads(
            (store.workflow_dir(workflow_id) / ".bioimageflow/draft.json").read_text()
        )
        assert document["graph"]["schema_version"] == 2
        assert draft["graph"]["schema_version"] == 2
        assert draft["dirty_against_saved"] is expected_dirty
        assert draft["base_saved_revision"] == document["artifact_hash"]
    assert json.loads(snapshot_path.read_text())["graph"]["schema_version"] == 2


def test_interrupted_migration_forward_recovers_and_rejects_forged_target(
    tmp_path, monkeypatch
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="wf"))
    path = store.workflow_dir("wf") / "workflow.json"
    raw = json.loads(path.read_text())
    raw["graph"] = _downgrade(raw["graph"])
    path.write_text(json.dumps(raw))
    real_apply = store._apply_schema_v2_targets

    def interrupt(targets):
        real_apply(targets[:1])
        raise OSError("crash after first target")

    monkeypatch.setattr(store, "_apply_schema_v2_targets", interrupt)
    with pytest.raises(OSError, match="crash"):
        store.migrate_schema_v2_workflows()
    assert store._schema_v2_migration_journal_path.is_file()

    restarted = _store(tmp_path)
    restarted.migrate_schema_v2_workflows()
    assert not restarted._schema_v2_migration_journal_path.exists()
    assert json.loads(path.read_text())["graph"]["schema_version"] == 2

    forged = {
        "version": 1,
        "targets": [
            {
                "kind": "saved_workflow",
                "path": "settings.json",
                "payload": {},
                "digest": "sha256:" + "0" * 64,
            }
        ],
    }
    restarted._schema_v2_migration_journal_path.write_text(json.dumps(forged))
    with pytest.raises(WorkflowMoveRecoveryError, match="not an authorized"):
        restarted.migrate_schema_v2_workflows()

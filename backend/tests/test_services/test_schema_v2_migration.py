from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import NestedSnapshotOwner
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.services.workflow_artifacts import artifact_hash
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import (
    WorkflowFormatPlanStaleError,
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


def _recursive_graph(base: GraphState) -> GraphState:
    grandchild = base.model_dump(mode="json", by_alias=True, exclude_none=True)
    grandchild.update(name="grandchild", display_name="Grandchild")
    child = deepcopy(grandchild)
    child.update(name="child", display_name="Child")
    child["nodes"] = [
        {
            "type": "workflow",
            "id": "grandchild-node",
            "name": "Grandchild node",
            "workflow": grandchild,
            "bindings": {},
            "position": [20, 30],
        }
    ]
    root = deepcopy(child)
    root.update(name="root", display_name="Root")
    root["nodes"] = [
        {
            "type": "workflow",
            "id": "child",
            "name": "Child node",
            "workflow": child,
            "bindings": {},
            "position": [40, 50],
        }
    ]
    return GraphState.model_validate(root)


def _assert_recursive_schema_v2(graph: dict) -> None:
    assert graph["schema_version"] == 2
    [child] = graph["nodes"]
    assert child["type"] == "workflow"
    assert child["workflow"]["schema_version"] == 2
    [grandchild] = child["workflow"]["nodes"]
    assert grandchild["type"] == "workflow"
    assert grandchild["workflow"]["schema_version"] == 2


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
        store.save_workflow(
            workflow_id,
            WorkflowSaveBody(graph=_recursive_graph(store.get_workflow(workflow_id).graph)),
        )

    clean_graph = store.get_workflow("clean").graph
    clean_child = clean_graph.nodes[0].workflow
    private_child = clean_child.model_dump(mode="json", by_alias=True, exclude_none=True)
    private_child["nodes"][0]["workflow"]["display_name"] = "Private grandchild"
    private_child_graph = GraphState.model_validate(private_child)
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    opened = snapshots.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="workflow:clean",
            workflow_id="clean",
            identity_generation=store.workflow_generation("clean"),
        ),
        "child",
        clean_child,
    )
    assert opened.snapshot_revision == 0
    opened = snapshots.put_snapshot(
        opened.session_id,
        expected_revision=opened.snapshot_revision,
        graph=private_child_graph,
    )
    assert opened.snapshot_revision == 1
    assert opened.validation.valid is True
    assert store.get_workflow("clean").graph == clean_graph
    snapshot_path = (
        store.workspace_dir
        / ".bioimageflow/nested-workflow-snapshots"
        / f"{opened.session_id}.json"
    )
    generation_before = {
        workflow_id: store.workflow_generation(workflow_id) for workflow_id in ("clean", "dirty")
    }
    snapshot_identity_before = (
        opened.session_id,
        opened.owner,
        opened.parent_node_id,
        opened.snapshot_revision,
    )
    saved_graphs = {
        workflow_id: store.get_workflow(workflow_id).graph.model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        for workflow_id in ("clean", "dirty")
    }
    expected_draft_graphs = deepcopy(saved_graphs)
    expected_draft_graphs["dirty"]["nodes"][0]["workflow"]["nodes"][0]["workflow"][
        "display_name"
    ] = "Draft grandchild"

    for workflow_id in ("clean", "dirty"):
        path = store.workflow_dir(workflow_id) / "workflow.json"
        raw = json.loads(path.read_text())
        raw["graph"] = _downgrade(raw["graph"])
        raw["artifact_hash"] = "sha256:" + ("1" if workflow_id == "clean" else "2") * 64
        path.write_text(json.dumps(raw))
        draft_graph = _downgrade(expected_draft_graphs[workflow_id])
        _write_draft(
            store,
            workflow_id,
            draft_graph,
            raw["artifact_hash"],
            dirty=workflow_id == "dirty",
        )

    raw_snapshot = json.loads(snapshot_path.read_text())
    raw_snapshot["graph"] = _downgrade(private_child)
    snapshot_path.write_text(json.dumps(raw_snapshot))

    migration_sources = [
        *(store.workflow_dir(workflow_id) / "workflow.json" for workflow_id in ("clean", "dirty")),
        *(
            store.workflow_dir(workflow_id) / ".bioimageflow/draft.json"
            for workflow_id in ("clean", "dirty")
        ),
        snapshot_path,
    ]
    before = {path: path.read_bytes() for path in migration_sources}
    preview = store.workflow_format_status()
    assert preview.pending_plan_id is not None
    assert {notice.workflow_id for notice in preview.notices if notice.status == "pending"} == {
        "clean",
        "dirty",
    }
    assert {path: path.read_bytes() for path in before} == before
    assert [workflow.id for workflow in store.list_workflows()] == []

    applied = store.apply_workflow_format_migrations(preview.pending_plan_id)
    backup_paths = [Path(path) for notice in applied.notices for path in notice.backup_paths]
    expected_backup_root = (
        store.workspace_dir
        / ".bioimageflow/backups/workflow-format"
        / preview.pending_plan_id.replace(":", "-")
    )
    assert set(backup_paths) == {
        expected_backup_root / path.relative_to(store.workspace_dir) for path in before
    }
    for source, original_bytes in before.items():
        backup = expected_backup_root / source.relative_to(store.workspace_dir)
        assert backup.read_bytes() == original_bytes

    restarted = _store(tmp_path)
    for workflow_id, expected_dirty in (("clean", False), ("dirty", True)):
        document = json.loads((store.workflow_dir(workflow_id) / "workflow.json").read_text())
        draft = json.loads(
            (store.workflow_dir(workflow_id) / ".bioimageflow/draft.json").read_text()
        )
        _assert_recursive_schema_v2(document["graph"])
        _assert_recursive_schema_v2(draft["graph"])
        assert document["graph"] == saved_graphs[workflow_id]
        assert draft["graph"] == expected_draft_graphs[workflow_id]
        assert draft["dirty_against_saved"] is expected_dirty
        assert draft["base_saved_revision"] == document["artifact_hash"]
        assert draft["draft_revision"] == 4
        assert document["artifact_hash"] == artifact_hash(
            GraphState.model_validate(saved_graphs[workflow_id]), []
        )
        assert restarted.workflow_generation(workflow_id) == generation_before[workflow_id]
        reopened_document = restarted.get_workflow(workflow_id)
        assert reopened_document.artifact_hash == document["artifact_hash"]
        reopened_draft = json.loads(
            (restarted.workflow_dir(workflow_id) / ".bioimageflow/draft.json").read_text()
        )
        assert reopened_draft == draft
        draft_hash = artifact_hash(GraphState.model_validate(draft["graph"]), [])
        if expected_dirty:
            assert draft_hash != document["artifact_hash"]
        else:
            assert draft["graph"] == document["graph"]
            assert draft_hash == document["artifact_hash"]
    reopened_snapshot = NestedWorkflowSnapshotService(lambda: restarted).get_snapshot(
        opened.session_id
    )
    reopened_snapshot_graph = reopened_snapshot.graph.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    assert reopened_snapshot_graph == private_child
    assert reopened_snapshot_graph["nodes"][0]["workflow"]["schema_version"] == 2
    assert (
        reopened_snapshot.session_id,
        reopened_snapshot.owner,
        reopened_snapshot.parent_node_id,
        reopened_snapshot.snapshot_revision,
    ) == snapshot_identity_before


def test_interrupted_migration_forward_recovers_and_rejects_forged_target(
    tmp_path, monkeypatch
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="wf"))
    store.save_workflow(
        "wf", WorkflowSaveBody(graph=_recursive_graph(store.get_workflow("wf").graph))
    )
    generation = store.workflow_generation("wf")
    graph = store.get_workflow("wf").graph
    opened = NestedWorkflowSnapshotService(lambda: store).open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="workflow:wf",
            workflow_id="wf",
            identity_generation=generation,
        ),
        "child",
        graph.nodes[0].workflow,
    )
    snapshot_path = (
        store.workspace_dir
        / ".bioimageflow/nested-workflow-snapshots"
        / f"{opened.session_id}.json"
    )
    path = store.workflow_dir("wf") / "workflow.json"
    raw = json.loads(path.read_text())
    raw["graph"] = _downgrade(raw["graph"])
    path.write_text(json.dumps(raw))
    draft_path = store.workflow_dir("wf") / ".bioimageflow/draft.json"
    _write_draft(store, "wf", raw["graph"], raw["artifact_hash"], dirty=False)
    raw_snapshot = json.loads(snapshot_path.read_text())
    raw_snapshot["graph"] = _downgrade(raw_snapshot["graph"])
    snapshot_path.write_text(json.dumps(raw_snapshot))
    original_bytes = {
        authority: authority.read_bytes() for authority in (path, draft_path, snapshot_path)
    }
    plan_id = store.workflow_format_status().pending_plan_id
    assert plan_id is not None
    real_apply = store._apply_schema_v2_targets

    def interrupt(targets, *, plan_id):
        assert len(targets) == 3
        [draft_target] = [target for target in targets if target["kind"] == "root_draft"]
        real_apply([draft_target], plan_id=plan_id)
        raise OSError("crash after draft target")

    monkeypatch.setattr(store, "_apply_schema_v2_targets", interrupt)
    with pytest.raises(OSError, match="crash after draft target"):
        store.apply_workflow_format_migrations(plan_id)
    assert store._schema_v2_migration_journal_path.is_file()
    assert path.read_bytes() == original_bytes[path]
    migrated_draft_bytes = draft_path.read_bytes()
    migrated_draft_digest = hashlib.sha256(migrated_draft_bytes).hexdigest()
    _assert_recursive_schema_v2(json.loads(migrated_draft_bytes)["graph"])
    assert snapshot_path.read_bytes() == original_bytes[snapshot_path]
    backup_root = (
        store.workspace_dir / ".bioimageflow/backups/workflow-format" / plan_id.replace(":", "-")
    )
    for authority, content in original_bytes.items():
        assert (backup_root / authority.relative_to(store.workspace_dir)).read_bytes() == content

    restarted = _store(tmp_path)
    restarted.recover_workflow_format_migration()
    assert not restarted._schema_v2_migration_journal_path.exists()
    assert draft_path.read_bytes() == migrated_draft_bytes
    assert hashlib.sha256(draft_path.read_bytes()).hexdigest() == migrated_draft_digest
    document = json.loads(path.read_text())
    draft = json.loads(draft_path.read_text())
    snapshot = NestedWorkflowSnapshotService(lambda: restarted).get_snapshot(opened.session_id)
    _assert_recursive_schema_v2(document["graph"])
    _assert_recursive_schema_v2(draft["graph"])
    assert snapshot.graph.schema_version == 2
    assert snapshot.graph.nodes[0].workflow.schema_version == 2
    assert draft["base_saved_revision"] == document["artifact_hash"]
    assert draft["dirty_against_saved"] is False
    assert draft["draft_revision"] == 4
    assert restarted.workflow_generation("wf") == generation
    assert restarted.get_workflow("wf").artifact_hash == document["artifact_hash"]
    assert (snapshot.session_id, snapshot.owner, snapshot.snapshot_revision) == (
        opened.session_id,
        opened.owner,
        opened.snapshot_revision,
    )

    forged = {
        "version": 2,
        "confirmed": True,
        "plan_id": "sha256:" + "0" * 64,
        "targets": [
            {
                "kind": "saved_workflow",
                "path": "settings.json",
                "source_digest": "sha256:" + "0" * 64,
                "backup_path": ".bioimageflow/backups/workflow-format/bad/settings.json",
                "target_payload": {},
                "target_digest": "sha256:" + "0" * 64,
            }
        ],
    }
    restarted._schema_v2_migration_journal_path.write_text(json.dumps(forged))
    with pytest.raises(WorkflowMoveRecoveryError, match="not an authorized"):
        restarted.recover_workflow_format_migration()


def test_changed_draft_refuses_preview_without_replacing_any_authority(tmp_path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="pending"))
    store.create_workflow(WorkflowCreate(name="current"))
    pending_path = store.workflow_dir("pending") / "workflow.json"
    current_path = store.workflow_dir("current") / "workflow.json"
    raw = json.loads(pending_path.read_text())
    raw["graph"] = _downgrade(raw["graph"])
    pending_path.write_text(json.dumps(raw))
    _write_draft(store, "pending", raw["graph"], raw["artifact_hash"], dirty=False)
    draft_path = store.workflow_dir("pending") / ".bioimageflow/draft.json"
    plan_id = store.workflow_format_status().pending_plan_id
    assert plan_id is not None
    current_bytes = current_path.read_bytes()
    changed_draft = json.loads(draft_path.read_text())
    changed_draft["updated_at"] = "2026-09-15T10:01:00Z"
    draft_path.write_text(json.dumps(changed_draft))
    pending_bytes = pending_path.read_bytes()
    draft_bytes = draft_path.read_bytes()

    with pytest.raises(WorkflowFormatPlanStaleError, match="review again"):
        store.apply_workflow_format_migrations(plan_id)

    assert pending_path.read_bytes() == pending_bytes
    assert draft_path.read_bytes() == draft_bytes
    assert current_path.read_bytes() == current_bytes
    assert store.get_workflow("current").info.id == "current"
    assert store.workflow_format_status().pending_plan_id != plan_id
    assert not (store.workspace_dir / ".bioimageflow/backups/workflow-format").exists()


def test_invalid_editing_artifact_is_reported_separately_from_pending_updates(
    tmp_path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="pending"))
    store.create_workflow(WorkflowCreate(name="bad-draft"))
    pending_path = store.workflow_dir("pending") / "workflow.json"
    raw_pending = json.loads(pending_path.read_text())
    raw_pending["graph"] = _downgrade(raw_pending["graph"])
    pending_path.write_text(json.dumps(raw_pending))
    bad_draft_path = store.workflow_dir("bad-draft") / ".bioimageflow/draft.json"
    bad_draft_path.parent.mkdir()
    bad_draft_path.write_text("{not json")

    preview = store.workflow_format_status()

    assert preview.pending_plan_id is not None
    assert {(notice.status, notice.workflow_id) for notice in preview.notices} == {
        ("pending", "pending"),
        ("error", "bad-draft"),
    }
    error = next(notice for notice in preview.notices if notice.status == "error")
    assert error.path == str(bad_draft_path)
    assert "editing draft" in error.detail

    applied = store.apply_workflow_format_migrations(preview.pending_plan_id)

    assert {(notice.status, notice.workflow_id) for notice in applied.notices} == {
        ("migrated", "pending"),
        ("error", "bad-draft"),
    }
    assert bad_draft_path.read_text() == "{not json"

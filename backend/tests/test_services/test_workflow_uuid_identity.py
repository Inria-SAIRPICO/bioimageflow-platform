"""Persistent workflow identities remain independent of filesystem locations."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import UUID

import pytest

from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody, WorkflowUpdate
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import (
    WorkflowCreationDestinationChangedError,
    WorkflowIdentityConflictError,
    WorkflowStoreService,
)


def store_at(root: Path) -> WorkflowStoreService:
    return WorkflowStoreService(root / "workflows", ToolRegistryService())


def finish_move(store: WorkflowStoreService, operation_id: UUID) -> None:
    store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")
    store.mark_workflow_move_phase(operation_id, "preferences_rewritten")
    store.complete_workflow_move(operation_id)


def test_move_and_external_move_preserve_uuid_and_generation(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="old/demo"))
    before = store.get_workflow(original.id)
    patch = WorkflowUpdate(action="update", new_id="new/demo")
    operation_id = store.prepare_workflow_patch_move(original.id, patch)
    assert operation_id is not None
    moved = store.patch_workflow(original.id, patch, move_operation_id=operation_id)
    finish_move(store, operation_id)
    assert moved.id == original.id
    assert moved.identity_generation == original.identity_generation
    assert moved.relative_path == "new/demo"
    assert store.get_workflow(original.id).artifact_hash == before.artifact_hash
    store.workflow_dir(original.id).rename(tmp_path / "workflows" / "external")
    loaded = store.get_workflow(original.id)
    assert loaded.info.relative_path == "external"
    store.save_workflow(original.id, WorkflowSaveBody(graph=loaded.graph))
    assert not (tmp_path / "workflows" / "old" / "demo").exists()
    assert not (tmp_path / "workflows" / "new" / "demo").exists()


def test_copied_uuid_is_a_conflict_and_paths_are_not_addresses(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="demo"))
    with pytest.raises(FileNotFoundError):
        store.get_workflow("demo")
    shutil.copytree(store.workflow_dir(original.id), tmp_path / "workflows" / "copy")
    with pytest.raises(WorkflowIdentityConflictError):
        store.get_workflow(original.id)
    with pytest.raises(WorkflowIdentityConflictError):
        store.save_workflow(original.id, WorkflowSaveBody(graph=store._read_raw("demo")["graph"]))


def test_duplicate_allocates_new_uuid(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="demo"))
    copied = store.patch_workflow(original.id, WorkflowUpdate(action="duplicate", new_name="copy"))
    assert copied.id != original.id
    assert str(UUID(copied.id)) == copied.id
    assert copied.relative_path == "copy"


def test_creation_refuses_vanished_selected_folder_and_switched_workspace(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    store.create_folder("selected")
    (store.root_dir / "selected").rmdir()
    with pytest.raises(WorkflowCreationDestinationChangedError):
        store.create_workflow(WorkflowCreate(name="selected/demo", expected_parent_path="selected"))
    assert not (store.root_dir / "selected").exists()
    with pytest.raises(WorkflowCreationDestinationChangedError):
        store.create_workflow(WorkflowCreate(name="demo", expected_workspace_path=str(tmp_path / "other")))
    assert not (store.root_dir / "demo").exists()


def test_identity_migration_is_confirmed_backed_up_and_preserves_hash(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="folder/demo"))
    path = Path(original.path)
    raw = json.loads(path.read_text())
    raw.pop("workflow_id")
    raw["platform_document_version"] = 1
    path.write_text(json.dumps(raw))
    before = path.read_bytes()
    status = store.workflow_format_status()
    assert status.pending_plan_id is not None
    assert path.read_bytes() == before
    assert store.list_workflows() == []
    assert store.workflow_format_status().pending_plan_id == status.pending_plan_id
    applied = store.apply_workflow_format_migrations(status.pending_plan_id)
    identity = applied.identity_migrations[0].workflow_id
    loaded = store.get_workflow(identity)
    assert loaded.artifact_hash == raw["artifact_hash"]
    assert loaded.info.relative_path == "folder/demo"
    backups = [Path(item) for notice in applied.notices for item in notice.backup_paths]
    assert any(item.read_bytes() == before for item in backups)
    assert applied.pending_plan_id is None
    assert applied.identity_migration_id is not None
    ack = store.acknowledge_identity_migrations(applied.identity_migration_id, applied.identity_migrations)
    assert ack.identity_migrations == []


def test_recreating_identical_legacy_bytes_never_revives_deleted_uuid(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="demo"))
    path = Path(original.path)
    raw = json.loads(path.read_text())
    raw.pop("workflow_id")
    raw["platform_document_version"] = 1
    legacy = json.dumps(raw)
    path.write_text(legacy)
    first_status = store.workflow_format_status()
    assert first_status.pending_plan_id is not None
    first = store.apply_workflow_format_migrations(first_status.pending_plan_id)
    first_id = first.identity_migrations[0].workflow_id
    store.delete_workflow(first_id)
    path.parent.mkdir()
    path.write_text(legacy)
    second_status = store.workflow_format_status()
    assert second_status.pending_plan_id is not None
    second = store.apply_workflow_format_migrations(second_status.pending_plan_id)
    assert second.identity_migrations[0].workflow_id != first_id
    with pytest.raises(FileNotFoundError):
        store.get_workflow(first_id)


def test_move_preserves_dirty_draft_and_private_snapshot_revisions(tmp_path: Path) -> None:
    from bioimageflow_server.models.nested_workflow_snapshot import NestedSnapshotOwner
    from bioimageflow_server.services.nested_workflow_snapshot import NestedWorkflowSnapshotService
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="source/demo"))
    drafts = WorkflowDraftService(lambda: store)
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    graph = store.get_workflow(original.id).graph
    pending = graph.model_copy(update={"display_name": "Unsaved title"})
    accepted = drafts.put_draft(original.id, graph=pending, expected_revision=0, should_validate=False)
    snapshot = snapshots.open_snapshot(NestedSnapshotOwner(
        kind="root", canvas_id=f"workflow:{original.id}", workflow_id=original.id,
    ), "child", graph)
    draft_bytes = (store.workflow_dir(original.id) / ".bioimageflow" / "draft.json").read_bytes()
    operation = store.prepare_folder_rename_move("source", "moved")
    assert operation is not None
    store.rename_folder("source", "moved", move_operation_id=operation)
    finish_move(store, operation)
    after = drafts.get_draft_snapshot(original.id)
    assert after.draft_revision == accepted.draft_revision
    assert after.base_saved_revision == accepted.base_saved_revision
    assert after.dirty_against_saved
    assert after.graph == pending
    assert snapshots.get_snapshot(snapshot.session_id) == snapshot
    assert (store.workflow_dir(original.id) / ".bioimageflow" / "draft.json").read_bytes() == draft_bytes


def test_interrupted_identity_migration_finishes_same_uuid_and_preserves_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="demo"))
    drafts = WorkflowDraftService(lambda: store)
    graph = store.get_workflow(original.id).graph
    draft = drafts.put_draft(original.id, graph=graph.model_copy(update={"display_name": "Pending"}), expected_revision=0, should_validate=False)
    path = Path(original.path)
    raw = json.loads(path.read_text())
    raw.pop("workflow_id")
    raw["platform_document_version"] = 1
    path.write_text(json.dumps(raw))
    draft_path = path.parent / ".bioimageflow" / "draft.json"
    old_draft = json.loads(draft_path.read_text())
    old_draft["workflow_id"] = "demo"
    draft_path.write_text(json.dumps(old_draft))
    status = store.workflow_format_status()
    assert status.pending_plan_id is not None
    writer = store._write_schema_v2_json

    def interrupt(target: Path, payload: dict) -> None:
        if target == draft_path:
            raise OSError("interrupted after saved document publication")
        writer(target, payload)

    monkeypatch.setattr(store, "_write_schema_v2_json", interrupt)
    with pytest.raises(OSError, match="interrupted"):
        store.apply_workflow_format_migrations(status.pending_plan_id)
    assigned = json.loads(path.read_text())["workflow_id"]
    reopened = store_at(tmp_path)
    reopened.recover_workflow_format_migration()
    loaded = WorkflowDraftService(lambda: reopened).get_draft_snapshot(assigned)
    assert loaded.workflow_id == assigned
    assert loaded.graph == draft.graph
    assert loaded.draft_revision == draft.draft_revision
    assert loaded.base_saved_revision == draft.base_saved_revision
    assert loaded.dirty_against_saved == draft.dirty_against_saved
    assert reopened.workflow_format_status().pending_plan_id is None


def test_confirmed_legacy_move_finishes_before_uuid_format_migration(tmp_path: Path) -> None:
    from uuid import uuid4

    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="source"))
    path = Path(original.path)
    raw = json.loads(path.read_text())
    raw.pop("workflow_id")
    raw["platform_document_version"] = 1
    path.write_text(json.dumps(raw))
    store._write_workflow_generation_ledger({"source": 1})
    operation = uuid4()
    journal = {
        "journal_version": 1, "operation_id": str(operation),
        "operation_kind": "direct_workflow_move", "phase": "prepared",
        "source_path": "source", "destination_path": "folder/moved",
        "moves": [{
            "source_workflow_id": "source", "destination_workflow_id": "folder/moved",
            "source_generation_before": 1, "source_generation_after": 2,
            "destination_generation_before": 0, "destination_generation_after": 1,
            "target_metadata": {}, "target_display_name": "source",
        }], "promotion_children": [],
    }
    store._workflow_move_journal_path.write_text(json.dumps(journal))
    recovered = store.recover_pending_workflow_move()
    assert recovered is not None
    assert recovered.phase == "artifacts_rewritten"
    destination = store.root_dir / "folder" / "moved" / "workflow.json"
    assert destination.is_file()
    assert json.loads(destination.read_text())["platform_document_version"] == 1
    assert not path.exists()
    finish_move(store, operation)
    status = store.workflow_format_status()
    assert status.pending_plan_id is not None
    migrated = store.apply_workflow_format_migrations(status.pending_plan_id)
    loaded = store.get_workflow(migrated.identity_migrations[0].workflow_id)
    assert loaded.info.relative_path == "folder/moved"
    assert loaded.artifact_hash == raw["artifact_hash"]


def test_legacy_nested_owner_from_reused_path_blocks_migration_without_rebinding(tmp_path: Path) -> None:
    from bioimageflow_server.models.nested_workflow_snapshot import NestedSnapshotOwner
    from bioimageflow_server.services.nested_workflow_snapshot import NestedWorkflowSnapshotService

    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="demo"))
    snapshot_service = NestedWorkflowSnapshotService(lambda: store)
    snapshot = snapshot_service.open_snapshot(NestedSnapshotOwner(
        kind="root", canvas_id=f"workflow:{original.id}", workflow_id=original.id,
    ), "child", store.get_workflow(original.id).graph)
    snapshot_path = store.workspace_dir / ".bioimageflow" / "nested-workflow-snapshots" / f"{snapshot.session_id}.json"
    stale = json.loads(snapshot_path.read_text())
    stale["owner"] = {**stale["owner"], "workflow_id": "demo", "identity_generation": 1}
    snapshot_path.write_text(json.dumps(stale))
    path = Path(original.path)
    raw = json.loads(path.read_text())
    raw.pop("workflow_id")
    raw["platform_document_version"] = 1
    path.write_text(json.dumps(raw))
    store._write_workflow_generation_ledger({"demo": 3})
    store = store_at(tmp_path)
    before = path.read_bytes(), snapshot_path.read_bytes()
    status = store.workflow_format_status()
    assert status.pending_plan_id is None
    assert any("unresolved workflow incarnation" in notice.detail for notice in status.notices)
    assert (path.read_bytes(), snapshot_path.read_bytes()) == before


def test_reused_path_provenance_stays_unresolved_instead_of_binding_new_owner(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    source = store.create_workflow(WorkflowCreate(name="source"))
    parent = store.create_workflow(WorkflowCreate(name="parent"))
    source_document = store.get_workflow(source.id)
    parent_path = Path(parent.path)
    raw_parent = json.loads(parent_path.read_text())
    raw_parent["graph"]["nodes"] = [{
        "type": "workflow", "id": "child", "name": "Child", "position": [0, 0],
        "workflow": source_document.graph.model_dump(mode="json"), "bindings": {},
        "source": {"kind": "workspace", "workflow_id": "source", "artifact_hash": source_document.artifact_hash},
    }]
    # Save canonical content first so its existing artifact baseline is meaningful.
    store.save_workflow(parent.id, WorkflowSaveBody(graph=raw_parent["graph"]))
    for path in (Path(source.path), parent_path):
        raw = json.loads(path.read_text())
        raw.pop("workflow_id")
        raw["platform_document_version"] = 1
        path.write_text(json.dumps(raw))
    store._write_workflow_generation_ledger({"source": 3, "parent": 1})
    store = store_at(tmp_path)
    status = store.workflow_format_status()
    assert status.pending_plan_id is not None
    result = store.apply_workflow_format_migrations(status.pending_plan_id)
    parent_id = next(entry.workflow_id for entry in result.identity_migrations if entry.old_path == "parent")
    graph = store.get_workflow(parent_id).graph
    assert graph.nodes[0].source.workflow_id == "source"  # type: ignore[union-attr]
    with pytest.raises(FileNotFoundError):
        store.get_workflow("source")


def test_active_reference_migration_block_is_a_diagnostic_not_a_write(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="demo"))
    path = Path(original.path)
    raw = json.loads(path.read_text())
    raw.pop("workflow_id")
    raw["platform_document_version"] = 1
    path.write_text(json.dumps(raw))
    before = path.read_bytes()

    def blocked(_identities: dict) -> list:
        raise ValueError("blocked by active execution")

    store.configure_identity_migration_artifacts(blocked, {})
    status = store.workflow_format_status()
    assert status.pending_plan_id is None
    assert any("blocked by active execution" in notice.detail for notice in status.notices)
    assert path.read_bytes() == before

"""Crash-recovery regressions for workflow identity moves."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.services import workflow_store as workflow_store_module
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import (
    WorkflowMoveRecoveryError,
    WorkflowStoreService,
)


def _store(tmp_path: Path) -> WorkflowStoreService:
    workspace = tmp_path / "workspace"
    return WorkflowStoreService(
        root_dir=workspace / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=workspace / "outputs",
    )


def _journal_path(store: WorkflowStoreService) -> Path:
    return store.workspace_dir / ".bioimageflow" / "workflow-move-journal.json"


def _workflow_json(store: WorkflowStoreService, workflow_id: str) -> Path:
    return store.workflow_dir(workflow_id) / "workflow.json"


def _draft_json(store: WorkflowStoreService, workflow_id: str) -> Path:
    return store.workflow_dir(workflow_id) / ".bioimageflow" / "draft.json"


def _draft_payload(workflow_id: str) -> dict[str, object]:
    return {
        "draft_version": 1,
        "workflow_id": workflow_id,
        "base_saved_revision": "sha256:before-move",
        "draft_revision": 7,
        "updated_at": "2026-07-17T08:00:00Z",
        "updated_by": "agent",
        "dirty_against_saved": True,
        "graph": {"nodes": [], "edges": []},
        "validation": {"valid": True, "node_statuses": {}, "errors": []},
        "future_compatible": {"preserve": [1, 2, 3]},
    }


def _write_draft(store: WorkflowStoreService, workflow_id: str) -> dict[str, object]:
    payload = _draft_payload(workflow_id)
    path = _draft_json(store, workflow_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _complete_without_snapshots(store: WorkflowStoreService, operation_id: UUID) -> None:
    store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")
    store.complete_workflow_move(operation_id)


def test_post_directory_rename_failure_recovers_metadata_draft_storage_and_generations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    created = store.create_workflow(
        WorkflowCreate(
            name="project/source",
            display_name="Before",
            description="old description",
        )
    )
    source_storage = Path(created.storage_path or "")
    source_storage.mkdir(parents=True)
    (source_storage / "result.txt").write_text("preserved", encoding="utf-8")
    original_draft = _write_draft(store, "project/source")
    patch = WorkflowUpdate(
        action="update",
        new_id="archive/destination",
        display_name="After",
        description="new description",
    )
    operation_id = store.prepare_workflow_patch_move("project/source", patch)
    assert operation_id is not None
    prepared = store.pending_workflow_move()
    assert prepared is not None

    def fail_after_directory_rename(_destination: Path, _workflow_id: str) -> None:
        raise OSError("injected post-directory-rename failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(
            workflow_store_module,
            "normalize_workflow_draft_identity",
            fail_after_directory_rename,
        )
        with pytest.raises(OSError, match="post-directory-rename"):
            store.patch_workflow(
                "project/source",
                patch,
                move_operation_id=operation_id,
            )

    assert not store.workflow_dir("project/source").exists()
    assert store.workflow_dir("archive/destination").exists()
    assert (
        json.loads(_draft_json(store, "archive/destination").read_text(encoding="utf-8"))[
            "workflow_id"
        ]
        == "project/source"
    )

    restarted = _store(tmp_path)
    recovered = restarted.recover_pending_workflow_move()

    assert recovered is not None
    assert recovered.operation_id == operation_id
    assert recovered.phase == "artifacts_rewritten"
    move = recovered.moves[0]
    assert restarted.workflow_generation("project/source") == move.source_generation_after
    assert restarted.workflow_generation("archive/destination") == move.destination_generation_after
    destination_storage = Path(move.managed_storage.destination_path)  # type: ignore[union-attr]
    assert not source_storage.exists()
    assert (destination_storage / "result.txt").read_text(encoding="utf-8") == "preserved"

    raw = json.loads(_workflow_json(restarted, "archive/destination").read_text())
    assert raw["metadata"] == move.target_metadata
    assert raw["metadata"]["display_name"] == "After"
    assert raw["metadata"]["description"] == "new description"
    assert raw["workflow"]["config"]["storage_path"] == str(destination_storage)
    recovered_draft = json.loads(
        _draft_json(restarted, "archive/destination").read_text(encoding="utf-8")
    )
    assert recovered_draft == {
        **original_draft,
        "workflow_id": "archive/destination",
    }

    workflow_bytes = _workflow_json(restarted, "archive/destination").read_bytes()
    draft_bytes = _draft_json(restarted, "archive/destination").read_bytes()
    recovered_again = restarted.recover_pending_workflow_move()
    assert recovered_again == recovered
    assert _workflow_json(restarted, "archive/destination").read_bytes() == workflow_bytes
    assert _draft_json(restarted, "archive/destination").read_bytes() == draft_bytes

    _complete_without_snapshots(restarted, operation_id)
    assert restarted.pending_workflow_move() is None


def test_generation_only_failure_rolls_forward_without_incrementing_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    created = store.create_workflow(WorkflowCreate(name="old"))
    storage = Path(created.storage_path or "")
    storage.mkdir(parents=True)
    (storage / "marker").write_text("kept", encoding="utf-8")
    patch = WorkflowUpdate(action="update", new_id="new")
    operation_id = store.prepare_workflow_patch_move("old", patch)
    assert operation_id is not None
    prepared = store.pending_workflow_move()
    assert prepared is not None
    move = prepared.moves[0]

    def fail_before_storage(_old_name: str, _new_name: str) -> str:
        raise OSError("injected generation-only failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "_move_managed_storage", fail_before_storage)
        with pytest.raises(OSError, match="generation-only"):
            store.patch_workflow(
                "old",
                patch,
                move_operation_id=operation_id,
            )

    assert store.workflow_dir("old").exists()
    assert not store.workflow_dir("new").exists()
    assert store.workflow_generation("old") == move.source_generation_after
    assert store.workflow_generation("new") == move.destination_generation_after

    recovered = _store(tmp_path).recover_pending_workflow_move()

    assert recovered is not None
    restarted = _store(tmp_path)
    assert restarted.workflow_generation("old") == move.source_generation_after
    assert restarted.workflow_generation("new") == move.destination_generation_after
    assert not restarted.workflow_dir("old").exists()
    assert restarted.workflow_dir("new").exists()
    assert (Path(move.managed_storage.destination_path) / "marker").read_text() == "kept"  # type: ignore[union-attr]


def test_recovery_reaffirms_existing_destination_parent_chain_before_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old"))
    patch = WorkflowUpdate(action="update", new_id="deep/nested/new")
    operation_id = store.prepare_workflow_patch_move("old", patch)
    assert operation_id is not None
    destination_parent = store.root_dir / "deep" / "nested"
    original_ensure = store._ensure_directory_durable

    def fail_after_mkdir(path: Path) -> None:
        if path == destination_parent:
            path.mkdir(parents=True, exist_ok=True)
            raise OSError("injected interruption before parent-chain fsync")
        original_ensure(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "_ensure_directory_durable", fail_after_mkdir)
        with pytest.raises(OSError, match="parent-chain fsync"):
            store.patch_workflow(
                "old",
                patch,
                move_operation_id=operation_id,
            )

    assert destination_parent.exists()
    assert store.workflow_dir("old").exists()
    restarted = _store(tmp_path)
    events: list[tuple[str, Path]] = []
    original_fsync = workflow_store_module._fsync_directory
    original_rename = Path.rename

    def record_fsync(path: Path) -> None:
        events.append(("fsync", path))
        original_fsync(path)

    def record_rename(path: Path, target: Path) -> Path:
        if path == restarted.workflow_dir("old"):
            events.append(("rename", Path(target)))
        return original_rename(path, target)

    with monkeypatch.context() as scoped:
        scoped.setattr(workflow_store_module, "_fsync_directory", record_fsync)
        scoped.setattr(Path, "rename", record_rename)
        restarted.recover_pending_workflow_move()

    rename_index = events.index(("rename", restarted.workflow_dir("deep/nested/new")))
    for directory in (
        destination_parent,
        destination_parent.parent,
        restarted.root_dir,
        restarted.root_dir.parent,
    ):
        assert events.index(("fsync", directory)) < rename_index


def test_legacy_generation_zero_move_commits_exactly_once(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store._write_raw("legacy", store._empty_raw(WorkflowCreate(name="legacy")))
    assert store.workflow_generation("legacy") == 0
    patch = WorkflowUpdate(action="update", new_id="current")
    operation_id = store.prepare_workflow_patch_move("legacy", patch)
    assert operation_id is not None
    prepared = store.pending_workflow_move()
    assert prepared is not None
    assert prepared.moves[0].source_generation_before == 0
    assert prepared.moves[0].destination_generation_before == 0

    store.patch_workflow(
        "legacy",
        patch,
        move_operation_id=operation_id,
    )
    store.mark_workflow_move_phase(operation_id, "artifacts_rewritten")
    store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")
    store.complete_workflow_move(operation_id)

    restarted = _store(tmp_path)
    assert restarted.workflow_generation("legacy") == 1
    assert restarted.workflow_generation("current") == 1
    assert restarted.get_workflow("current").info.identity_generation == 1


def test_prepared_but_unreserved_move_is_abandoned(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old"))
    operation_id = store.prepare_workflow_patch_move(
        "old",
        WorkflowUpdate(action="update", new_id="new"),
    )
    assert operation_id is not None

    recovered = store.recover_pending_workflow_move()

    assert recovered is None
    assert store.pending_workflow_move() is None
    assert store.workflow_dir("old").exists()
    assert not store.workflow_dir("new").exists()
    assert store.workflow_generation("old") == 1
    assert store.workflow_generation("new") == 0


def test_claimed_artifact_phase_with_untouched_generations_fails_closed(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old"))
    operation_id = store.prepare_workflow_patch_move(
        "old",
        WorkflowUpdate(action="update", new_id="new"),
    )
    assert operation_id is not None
    store.mark_workflow_move_phase(operation_id, "artifacts_rewritten")

    with pytest.raises(WorkflowMoveRecoveryError, match="phase claims committed"):
        store.recover_pending_workflow_move()

    assert store.workflow_dir("old").exists()
    assert not store.workflow_dir("new").exists()
    assert store.pending_workflow_move() is not None


def test_identity_move_executors_require_their_exact_prepared_journal(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old"))
    patch = WorkflowUpdate(action="update", new_id="new")

    with pytest.raises(WorkflowMoveRecoveryError, match="requires a prepared"):
        store.patch_workflow("old", patch)

    store.create_folder("project")
    with pytest.raises(WorkflowMoveRecoveryError, match="requires a prepared"):
        store.rename_folder("project", "archive")
    (store.root_dir / "project" / "note.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(WorkflowMoveRecoveryError, match="requires a prepared"):
        store.delete_folder("project", "move_children_up")

    assert store.workflow_dir("old").exists()
    assert (store.root_dir / "project" / "note.txt").read_text(encoding="utf-8") == "keep"


def test_prepared_direct_move_rejects_changed_patch_intent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old", display_name="Original"))
    prepared_patch = WorkflowUpdate(
        action="update",
        new_id="new",
        display_name="Prepared",
    )
    operation_id = store.prepare_workflow_patch_move("old", prepared_patch)
    assert operation_id is not None

    with pytest.raises(WorkflowMoveRecoveryError, match="metadata no longer matches"):
        store.patch_workflow(
            "old",
            WorkflowUpdate(
                action="update",
                new_id="new",
                display_name="Different",
            ),
            move_operation_id=operation_id,
        )

    assert store.get_workflow("old").info.display_name == "Original"
    assert not store.workflow_dir("new").exists()
    store.discard_workflow_move_if_unstarted(operation_id)


def test_pending_committed_move_fences_other_workflow_mutations(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old"))
    store.create_folder("spare-folder")
    patch = WorkflowUpdate(action="update", new_id="new")
    operation_id = store.prepare_workflow_patch_move("old", patch)
    assert operation_id is not None
    store.patch_workflow(
        "old",
        patch,
        move_operation_id=operation_id,
    )
    generation = store.workflow_generation("new")

    mutations = [
        lambda: store.create_workflow(WorkflowCreate(name="other")),
        lambda: store.create_folder("other-folder"),
        lambda: store.save_workflow(
            "new",
            WorkflowSaveBody(graph=GraphState(nodes=[], edges=[])),
        ),
        lambda: store.delete_workflow("new"),
        lambda: store.patch_workflow(
            "new",
            WorkflowUpdate(action="duplicate", new_name="copy"),
        ),
        lambda: store.rebind_versions("new"),
        lambda: store.delete_folder("spare-folder"),
    ]
    for mutation in mutations:
        with pytest.raises(WorkflowMoveRecoveryError, match="must recover"):
            mutation()

    assert store.workflow_generation("new") == generation
    assert store.workflow_dir("new").exists()
    assert not store.workflow_dir("other").exists()
    assert not store.workflow_dir("copy").exists()
    assert (store.root_dir / "spare-folder").exists()


def test_zero_workflow_promotion_uses_child_topology_as_commit_signal(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    folder = store.root_dir / "project"
    folder.mkdir(parents=True)
    (folder / "one.txt").write_text("one", encoding="utf-8")
    (folder / "two.txt").write_text("two", encoding="utf-8")
    operation_id = store.prepare_folder_promotion_move("project")
    assert operation_id is not None
    prepared = store.pending_workflow_move()
    assert prepared is not None
    assert prepared.moves == []
    assert {
        (child.source_relative_path, child.destination_relative_path)
        for child in prepared.promotion_children
    } == {("project/one.txt", "one.txt"), ("project/two.txt", "two.txt")}

    (folder / "one.txt").rename(store.root_dir / "one.txt")
    recovered = store.recover_pending_workflow_move()

    assert recovered is not None
    assert recovered.phase == "artifacts_rewritten"
    assert not folder.exists()
    assert (store.root_dir / "one.txt").read_text(encoding="utf-8") == "one"
    assert (store.root_dir / "two.txt").read_text(encoding="utf-8") == "two"


def test_recovery_fails_closed_when_both_workflow_paths_exist(tmp_path: Path) -> None:
    store = _store(tmp_path)
    created = store.create_workflow(WorkflowCreate(name="old"))
    source_storage = Path(created.storage_path or "")
    source_storage.mkdir(parents=True)
    (source_storage / "marker").write_text("source", encoding="utf-8")
    operation_id = store.prepare_workflow_patch_move(
        "old",
        WorkflowUpdate(action="update", new_id="new"),
    )
    assert operation_id is not None
    journal = store.pending_workflow_move()
    assert journal is not None
    store._reserve_workflow_generations(["old", "new"])
    destination = store.workflow_dir("new")
    destination.mkdir(parents=True)
    (destination / "collision.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(WorkflowMoveRecoveryError, match="exactly one source/destination"):
        store.recover_pending_workflow_move()

    assert store.workflow_dir("old").exists()
    assert (destination / "collision.txt").read_text(encoding="utf-8") == "do not overwrite"
    assert (source_storage / "marker").read_text(encoding="utf-8") == "source"
    assert store.pending_workflow_move() == journal


def test_corrupt_or_extra_field_journal_is_rejected_without_mutation(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old"))
    journal_path = _journal_path(store)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text('{"journal_version": 1, "unexpected": true}', encoding="utf-8")

    with pytest.raises(WorkflowMoveRecoveryError, match="Cannot trust"):
        store.pending_workflow_move()
    with pytest.raises(WorkflowMoveRecoveryError, match="Cannot trust"):
        store.prepare_workflow_patch_move(
            "old",
            WorkflowUpdate(action="update", new_id="new"),
        )

    assert store.workflow_dir("old").exists()
    assert not store.workflow_dir("new").exists()


def test_folder_preparations_capture_all_identity_and_child_mappings(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="project/a"))
    store.create_workflow(WorkflowCreate(name="project/nested/b"))

    rename_id = store.prepare_folder_rename_move("project", "archive")
    assert rename_id is not None
    rename = store.pending_workflow_move()
    assert rename is not None
    assert {(move.source_workflow_id, move.destination_workflow_id) for move in rename.moves} == {
        ("project/a", "archive/a"),
        ("project/nested/b", "archive/nested/b"),
    }
    store.discard_workflow_move_if_unstarted(rename_id)

    promotion_id = store.prepare_folder_promotion_move("project")
    assert promotion_id is not None
    promotion = store.pending_workflow_move()
    assert promotion is not None
    assert {
        (move.source_workflow_id, move.destination_workflow_id) for move in promotion.moves
    } == {("project/a", "a"), ("project/nested/b", "nested/b")}
    assert {
        (child.source_relative_path, child.destination_relative_path)
        for child in promotion.promotion_children
    } == {("project/a", "a"), ("project/nested", "nested")}

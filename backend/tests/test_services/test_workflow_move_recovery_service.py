"""Integration tests for store-and-snapshot move recovery coordination."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import NestedSnapshotOwner
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowUpdate
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
    RootWorkflowSnapshotMove,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_move_recovery import (
    WorkflowMoveRecoveryService,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _store(tmp_path: Path) -> WorkflowStoreService:
    workspace = tmp_path / "workspace"
    return WorkflowStoreService(
        root_dir=workspace / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=workspace / "outputs",
    )


def _empty_graph() -> GraphState:
    return GraphState(nodes=[], edges=[])


def test_recovery_moves_retained_snapshot_tree_before_clearing_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    created = store.create_workflow(WorkflowCreate(name="old"))
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    parent = snapshots.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="legacy-startup-alias",
            workflow_id="old",
        ),
        "nested-parent",
        _empty_graph(),
    )
    child = snapshots.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "nested-child",
        _empty_graph(),
    )
    patch = WorkflowUpdate(action="update", new_id="new")
    operation_id = store.prepare_workflow_patch_move("old", patch)
    assert operation_id is not None
    pending = store.pending_workflow_move()
    assert pending is not None
    move = pending.moves[0]

    def fail_after_generation_commit(_old_name: str, _new_name: str) -> str:
        raise OSError("injected interruption after generation commit")

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "_move_managed_storage", fail_after_generation_commit)
        with pytest.raises(OSError, match="generation commit"):
            store.patch_workflow(
                "old",
                patch,
                move_operation_id=operation_id,
            )

    restarted = _store(tmp_path)
    restarted_snapshots = NestedWorkflowSnapshotService(lambda: restarted)
    recovery = WorkflowMoveRecoveryService(lambda: restarted, restarted_snapshots)

    recovered = recovery.recover_pending_move()

    assert recovered is not None
    assert recovered.operation_id == operation_id
    assert restarted.pending_workflow_move() is None
    assert not restarted.workflow_dir("old").exists()
    assert restarted.workflow_dir("new").exists()
    assert restarted.workflow_generation("old") == move.source_generation_after
    assert restarted.workflow_generation("new") == move.destination_generation_after
    recovered_parent = restarted_snapshots.get_snapshot(parent.session_id)
    assert recovered_parent.owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:new",
        workflow_id="new",
        identity_generation=move.destination_generation_after,
    )
    assert restarted_snapshots.get_snapshot(child.session_id) == child
    assert recovery.recover_pending_move() is None
    assert restarted_snapshots.cleanup_orphaned_snapshots() == []
    assert created.identity_generation == move.source_generation_before


def test_unreadable_snapshot_fails_before_forward_recovery_and_keeps_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old"))
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    opened = snapshots.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="ignored", workflow_id="old"),
        "nested-parent",
        _empty_graph(),
    )
    patch = WorkflowUpdate(action="update", new_id="new")
    operation_id = store.prepare_workflow_patch_move("old", patch)
    assert operation_id is not None

    def fail_after_generation_commit(_old_name: str, _new_name: str) -> str:
        raise OSError("injected interruption after generation commit")

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "_move_managed_storage", fail_after_generation_commit)
        with pytest.raises(OSError, match="generation commit"):
            store.patch_workflow(
                "old",
                patch,
                move_operation_id=operation_id,
            )

    restarted = _store(tmp_path)
    restarted_snapshots = NestedWorkflowSnapshotService(lambda: restarted)
    original_read = restarted_snapshots._read_path

    def unreadable(path: Path):
        if path.name == f"{opened.session_id}.json":
            raise OSError("snapshot volume unavailable")
        return original_read(path)

    monkeypatch.setattr(restarted_snapshots, "_read_path", unreadable)
    recovery = WorkflowMoveRecoveryService(lambda: restarted, restarted_snapshots)

    with pytest.raises(OSError, match="retained snapshots are unreadable"):
        recovery.recover_pending_move()

    assert restarted.pending_workflow_move() is not None
    assert restarted.workflow_dir("old").exists()
    assert not restarted.workflow_dir("new").exists()


@pytest.mark.parametrize("snapshot_phase_recorded", [False, True])
def test_recovery_is_idempotent_after_snapshot_rewrite_boundary(
    tmp_path: Path,
    snapshot_phase_recorded: bool,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="old"))
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    opened = snapshots.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="ignored", workflow_id="old"),
        "nested-parent",
        _empty_graph(),
    )
    patch = WorkflowUpdate(action="update", new_id="new")
    operation_id = store.prepare_workflow_patch_move("old", patch)
    assert operation_id is not None
    prepared = store.pending_workflow_move()
    assert prepared is not None
    move = prepared.moves[0]
    store.patch_workflow(
        "old",
        patch,
        move_operation_id=operation_id,
    )
    store.mark_workflow_move_phase(operation_id, "artifacts_rewritten")
    snapshots.move_root_workflows(
        [
            RootWorkflowSnapshotMove(
                old_workflow_id="old",
                old_identity_generation=move.source_generation_before,
                new_workflow_id="new",
                new_identity_generation=move.destination_generation_after,
            )
        ]
    )
    if snapshot_phase_recorded:
        store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")

    restarted = _store(tmp_path)
    restarted_snapshots = NestedWorkflowSnapshotService(lambda: restarted)
    recovered = WorkflowMoveRecoveryService(
        lambda: restarted,
        restarted_snapshots,
    ).recover_pending_move()

    assert recovered is not None
    assert restarted.pending_workflow_move() is None
    assert restarted_snapshots.get_snapshot(opened.session_id).owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:new",
        workflow_id="new",
        identity_generation=move.destination_generation_after,
    )

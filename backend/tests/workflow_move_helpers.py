"""Test helpers for the production prepare/execute/finish move protocol."""

from __future__ import annotations

from uuid import UUID

from bioimageflow_server.models.workflow import (
    WorkflowFolderDelete,
    WorkflowFolderInfo,
    WorkflowInfo,
    WorkflowUpdate,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def finish_move_without_retained_snapshots(
    store: WorkflowStoreService,
    operation_id: UUID | None,
) -> None:
    """Finish a move in tests that deliberately have no retained snapshots."""

    if operation_id is None:
        return
    store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")
    store.complete_workflow_move(operation_id)


def execute_workflow_patch(
    store: WorkflowStoreService,
    name: str,
    patch: WorkflowUpdate,
) -> tuple[WorkflowInfo, UUID | None]:
    operation_id = store.prepare_workflow_patch_move(name, patch)
    try:
        info = store.patch_workflow(
            name,
            patch,
            move_operation_id=operation_id,
        )
    except Exception:
        if operation_id is not None:
            try:
                store.discard_workflow_move_if_unstarted(operation_id)
            except Exception:
                pass
        raise
    return info, operation_id


def patch_workflow(
    store: WorkflowStoreService,
    name: str,
    patch: WorkflowUpdate,
) -> WorkflowInfo:
    info, operation_id = execute_workflow_patch(store, name, patch)
    finish_move_without_retained_snapshots(store, operation_id)
    return info


def rename_folder(
    store: WorkflowStoreService,
    path: str,
    new_path: str,
) -> WorkflowFolderInfo:
    operation_id = store.prepare_folder_rename_move(path, new_path)
    assert operation_id is not None
    try:
        folder = store.rename_folder(
            path,
            new_path,
            move_operation_id=operation_id,
        )
    except Exception:
        try:
            store.discard_workflow_move_if_unstarted(operation_id)
        except Exception:
            pass
        raise
    finish_move_without_retained_snapshots(store, operation_id)
    return folder


def promote_folder(
    store: WorkflowStoreService,
    path: str,
    policy: WorkflowFolderDelete | str = "move_children_up",
) -> None:
    operation_id = store.prepare_folder_promotion_move(path)
    try:
        store.delete_folder(
            path,
            policy,
            move_operation_id=operation_id,
        )
    except Exception:
        if operation_id is not None:
            try:
                store.discard_workflow_move_if_unstarted(operation_id)
            except Exception:
                pass
        raise
    finish_move_without_retained_snapshots(store, operation_id)

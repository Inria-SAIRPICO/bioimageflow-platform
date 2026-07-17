"""Operation-specific coordination for durable workflow move recovery."""

from __future__ import annotations

from collections.abc import Callable

from bioimageflow_server.models.workflow_move_recovery import WorkflowMoveJournal
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
    RootWorkflowSnapshotMove,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService


class WorkflowMoveRecoveryService:
    """Finish one pending store-and-snapshot identity move before serving requests."""

    def __init__(
        self,
        workflow_store_provider: Callable[[], WorkflowStoreService],
        nested_snapshot_service: NestedWorkflowSnapshotService,
    ) -> None:
        self._workflow_store_provider = workflow_store_provider
        self._nested_snapshot_service = nested_snapshot_service

    def recover_pending_move(self) -> WorkflowMoveJournal | None:
        """Recover or abandon the current workspace's pending move atomically."""

        store = self._workflow_store_provider()
        with (
            self._nested_snapshot_service.snapshot_mutation(),
            store.workflow_structure_mutation(),
        ):
            pending = store.pending_workflow_move()
            if pending is None:
                return None

            current_generations = {
                workflow_id: store.workflow_generation(workflow_id)
                for move in pending.moves
                for workflow_id in (
                    move.source_workflow_id,
                    move.destination_workflow_id,
                )
            }
            expected_after = {
                move.source_workflow_id: move.source_generation_after for move in pending.moves
            } | {
                move.destination_workflow_id: move.destination_generation_after
                for move in pending.moves
            }
            if pending.moves and current_generations == expected_after:
                self._nested_snapshot_service.preflight_root_workflow_moves()

            recovered = store.recover_pending_workflow_move()
            if recovered is None:
                return None

            snapshot_moves = [
                RootWorkflowSnapshotMove(
                    old_workflow_id=move.source_workflow_id,
                    old_identity_generation=move.source_generation_before,
                    new_workflow_id=move.destination_workflow_id,
                    new_identity_generation=move.destination_generation_after,
                )
                for move in recovered.moves
            ]
            if snapshot_moves:
                self._nested_snapshot_service.preflight_root_workflow_moves()
                self._nested_snapshot_service.move_root_workflows(snapshot_moves)
            store.mark_workflow_move_phase(
                recovered.operation_id,
                "snapshots_rewritten",
            )
            store.complete_workflow_move(recovered.operation_id)
            return recovered

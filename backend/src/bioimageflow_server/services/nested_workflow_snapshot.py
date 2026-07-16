"""Durable private state for nested-workflow editor sessions."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedSnapshotOwner,
    NestedWorkflowSnapshotResponse,
)
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class NestedSnapshotRevisionConflict(ValueError):
    """Raised when a replacement or deletion targets a stale revision."""

    def __init__(
        self,
        *,
        expected_revision: int,
        current: NestedWorkflowSnapshotResponse,
    ) -> None:
        self.expected_revision = expected_revision
        self.current = current
        super().__init__(
            f"Nested snapshot revision conflict: expected {expected_revision}, "
            f"current is {current.snapshot_revision}"
        )


class NestedWorkflowSnapshotService:
    """Persist nested editor documents without changing their parent workflow."""

    def __init__(
        self,
        workflow_store_provider: Callable[[], WorkflowStoreService],
        *,
        fallback_storage_path_provider: Callable[[], Path | None] | None = None,
        dev_mode_provider: Callable[[], bool] | None = None,
        settings_provider: Callable[[], object | None] | None = None,
    ) -> None:
        self._workflow_store_provider = workflow_store_provider
        self._fallback_storage_path_provider = (
            fallback_storage_path_provider or (lambda: None)
        )
        self._dev_mode_provider = dev_mode_provider or (lambda: True)
        self._settings_provider = settings_provider or (lambda: None)
        self._lock = threading.RLock()

    def open_snapshot(
        self,
        owner: NestedSnapshotOwner,
        parent_node_id: str,
        graph: GraphState,
    ) -> NestedWorkflowSnapshotResponse:
        """Return the existing hierarchical session or create it atomically."""

        with self._lock:
            store = self._store()
            root_workflow_id = self._root_workflow_id(owner)
            for path in self._snapshot_dir(store).glob("*.json"):
                candidate = self._read_path(path)
                if candidate.owner == owner and candidate.parent_node_id == parent_node_id:
                    return candidate

            session_id = uuid.uuid4()
            response = NestedWorkflowSnapshotResponse(
                session_id=session_id,
                owner=owner,
                parent_node_id=parent_node_id,
                snapshot_revision=0,
                updated_at=_utc_now(),
                graph=graph,
                validation=self._validate(store, root_workflow_id, graph),
            )
            self._write(store, response)
            return response

    def get_snapshot(self, session_id: UUID) -> NestedWorkflowSnapshotResponse:
        with self._lock:
            return self._read(self._store(), session_id)

    def put_snapshot(
        self,
        session_id: UUID,
        *,
        expected_revision: int,
        graph: GraphState,
    ) -> NestedWorkflowSnapshotResponse:
        with self._lock:
            store = self._store()
            current = self._read(store, session_id)
            self._ensure_revision(current, expected_revision)
            root_workflow_id = self._root_workflow_id(current.owner)
            accepted = NestedWorkflowSnapshotResponse(
                session_id=current.session_id,
                owner=current.owner,
                parent_node_id=current.parent_node_id,
                snapshot_revision=current.snapshot_revision + 1,
                updated_at=_utc_now(),
                graph=graph,
                validation=self._validate(store, root_workflow_id, graph),
            )
            self._write(store, accepted)
            return accepted

    def delete_snapshot(self, session_id: UUID, *, expected_revision: int) -> None:
        with self._lock:
            store = self._store()
            current = self._read(store, session_id)
            self._ensure_revision(current, expected_revision)
            self._path(store, session_id).unlink()

    def _root_workflow_id(self, owner: NestedSnapshotOwner) -> str | None:
        if owner.kind == "root":
            if owner.workflow_id is not None:
                self._store().get_workflow(owner.workflow_id)
            return owner.workflow_id

        assert owner.session_id is not None
        visited: set[UUID] = set()
        current_session_id = owner.session_id
        while True:
            if current_session_id in visited:
                raise ValueError("Nested snapshot ownership cycle")
            visited.add(current_session_id)
            parent = self._read(self._store(), current_session_id)
            if parent.owner.kind == "root":
                if parent.owner.workflow_id is not None:
                    self._store().get_workflow(parent.owner.workflow_id)
                return parent.owner.workflow_id
            assert parent.owner.session_id is not None
            current_session_id = parent.owner.session_id

    def _validate(
        self,
        store: WorkflowStoreService,
        workflow_id: str | None,
        graph: GraphState,
    ) -> ValidationResult:
        storage_path = (
            store.get_storage_path(workflow_id)
            if workflow_id is not None
            else self._fallback_storage_path_provider()
        )
        return validate_graph(
            graph,
            store.tool_registry,
            storage_path=storage_path,
            dev_mode=self._dev_mode_provider(),
            settings=self._settings_provider(),
        )

    @staticmethod
    def _ensure_revision(
        current: NestedWorkflowSnapshotResponse,
        expected_revision: int,
    ) -> None:
        if current.snapshot_revision != expected_revision:
            raise NestedSnapshotRevisionConflict(
                expected_revision=expected_revision,
                current=current,
            )

    def _store(self) -> WorkflowStoreService:
        return self._workflow_store_provider()

    @staticmethod
    def _snapshot_dir(store: WorkflowStoreService) -> Path:
        return store.workspace_dir / ".bioimageflow" / "nested-workflow-snapshots"

    def _path(self, store: WorkflowStoreService, session_id: UUID) -> Path:
        return self._snapshot_dir(store) / f"{session_id}.json"

    def _read(
        self,
        store: WorkflowStoreService,
        session_id: UUID,
    ) -> NestedWorkflowSnapshotResponse:
        path = self._path(store, session_id)
        if not path.exists():
            raise FileNotFoundError(f"Nested snapshot not found: {session_id}")
        return self._read_path(path)

    @staticmethod
    def _read_path(path: Path) -> NestedWorkflowSnapshotResponse:
        return NestedWorkflowSnapshotResponse.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _write(
        self,
        store: WorkflowStoreService,
        snapshot: NestedWorkflowSnapshotResponse,
    ) -> None:
        path = self._path(store, snapshot.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{snapshot.session_id}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(snapshot.model_dump(mode="json"), handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

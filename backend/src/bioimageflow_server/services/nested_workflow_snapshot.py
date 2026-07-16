"""Durable private state for nested-workflow editor sessions."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from uuid import UUID

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedSnapshotOwner,
    NestedWorkflowSnapshotResponse,
)
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.graph_worker import run_graph_work
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


class NestedSnapshotHasDependents(ValueError):
    """Raised when deletion would orphan snapshots owned by this session."""

    def __init__(self, session_id: UUID, dependent_session_ids: list[UUID]) -> None:
        self.session_id = session_id
        self.dependent_session_ids = dependent_session_ids
        count = len(dependent_session_ids)
        super().__init__(
            f"Cannot delete nested snapshot {session_id}: {count} dependent nested "
            f"snapshot{'s' if count != 1 else ''} must be deleted first"
        )


@dataclass(frozen=True)
class _RootValidationContext:
    workflow_id: str | None
    identity_generation: int | None
    storage_path: Path | None


class NestedWorkflowSnapshotService:
    """Persist nested editor documents without changing their parent workflow."""

    def __init__(
        self,
        workflow_store_provider: Callable[[], WorkflowStoreService],
        *,
        fallback_storage_path_provider: Callable[[], Path | None] | None = None,
        dev_mode_provider: Callable[[], bool] | None = None,
        settings_provider: Callable[[], Settings | None] | None = None,
    ) -> None:
        self._workflow_store_provider = workflow_store_provider
        self._fallback_storage_path_provider = fallback_storage_path_provider or (lambda: None)
        self._dev_mode_provider = dev_mode_provider or (lambda: True)
        self._settings_provider = settings_provider or (lambda: None)
        self._lock = threading.RLock()

    @contextmanager
    def snapshot_mutation(self) -> Iterator[None]:
        """Hold the snapshot boundary before acquiring workflow identity locks."""

        with self._lock:
            yield

    def open_snapshot(
        self,
        owner: NestedSnapshotOwner,
        parent_node_id: str,
        graph: GraphState,
    ) -> NestedWorkflowSnapshotResponse:
        """Return the existing hierarchical session or create it atomically."""

        graph = graph.model_copy(deep=True)
        while True:
            store = self._store()
            with self._lock:
                root_context = self._root_validation_context_locked(store, owner)
                existing = self._find_snapshot(store, owner, parent_node_id)
                if existing is not None:
                    return existing
                session_id = uuid.uuid4()

            try:
                validation = self._validate(
                    store,
                    root_context.workflow_id,
                    graph,
                )
            except Exception:
                with self._lock:
                    existing = self._find_snapshot(store, owner, parent_node_id)
                    if existing is not None:
                        return existing
                    with self._root_validation_commit_locked(
                        store,
                        owner,
                        root_context,
                    ) as context_is_current:
                        if not context_is_current:
                            continue
                raise

            with self._lock:
                existing = self._find_snapshot(store, owner, parent_node_id)
                if existing is not None:
                    return existing
                with self._root_validation_commit_locked(
                    store,
                    owner,
                    root_context,
                ) as context_is_current:
                    if not context_is_current:
                        continue
                    response = NestedWorkflowSnapshotResponse(
                        session_id=session_id,
                        owner=owner,
                        parent_node_id=parent_node_id,
                        snapshot_revision=0,
                        updated_at=_utc_now(),
                        graph=graph,
                        validation=validation,
                    )
                    self._write(store, response)
                    return response

    async def open_snapshot_async(
        self,
        owner: NestedSnapshotOwner,
        parent_node_id: str,
        graph: GraphState,
    ) -> NestedWorkflowSnapshotResponse:
        """Open a snapshot without blocking the event loop."""

        graph = graph.model_copy(deep=True)
        return await run_graph_work(
            partial(
                self.open_snapshot,
                owner,
                parent_node_id,
                graph,
            )
        )

    def get_snapshot(self, session_id: UUID) -> NestedWorkflowSnapshotResponse:
        with self._lock:
            return self._read(self._store(), session_id)

    async def get_snapshot_async(
        self,
        session_id: UUID,
    ) -> NestedWorkflowSnapshotResponse:
        """Read a snapshot without blocking the event loop."""

        return await run_graph_work(partial(self.get_snapshot, session_id))

    def put_snapshot(
        self,
        session_id: UUID,
        *,
        expected_revision: int,
        graph: GraphState,
    ) -> NestedWorkflowSnapshotResponse:
        graph = graph.model_copy(deep=True)
        while True:
            with self._lock:
                store = self._store()
                current = self._read(store, session_id)
                self._ensure_revision(current, expected_revision)
                root_context = self._root_validation_context_locked(
                    store,
                    current.owner,
                )

            try:
                validation = self._validate(
                    store,
                    root_context.workflow_id,
                    graph,
                )
            except Exception:
                with self._lock:
                    current = self._read(store, session_id)
                    self._ensure_revision(current, expected_revision)
                    with self._root_validation_commit_locked(
                        store,
                        current.owner,
                        root_context,
                    ) as context_is_current:
                        if not context_is_current:
                            continue
                raise

            with self._lock:
                current = self._read(store, session_id)
                self._ensure_revision(current, expected_revision)
                with self._root_validation_commit_locked(
                    store,
                    current.owner,
                    root_context,
                ) as context_is_current:
                    if not context_is_current:
                        continue
                    accepted = NestedWorkflowSnapshotResponse(
                        session_id=current.session_id,
                        owner=current.owner,
                        parent_node_id=current.parent_node_id,
                        snapshot_revision=current.snapshot_revision + 1,
                        updated_at=_utc_now(),
                        graph=graph,
                        validation=validation,
                    )
                    self._write(store, accepted)
                    return accepted

    async def put_snapshot_async(
        self,
        session_id: UUID,
        *,
        expected_revision: int,
        graph: GraphState,
    ) -> NestedWorkflowSnapshotResponse:
        """Validate and commit a snapshot through the bounded graph worker."""

        graph = graph.model_copy(deep=True)
        return await run_graph_work(
            partial(
                self.put_snapshot,
                session_id,
                expected_revision=expected_revision,
                graph=graph,
            )
        )

    def delete_snapshot(self, session_id: UUID, *, expected_revision: int) -> None:
        with self._lock:
            store = self._store()
            current = self._read(store, session_id)
            self._ensure_revision(current, expected_revision)
            dependents = self._dependent_session_ids(store, session_id)
            if dependents:
                raise NestedSnapshotHasDependents(session_id, dependents)
            self._path(store, session_id).unlink()

    async def delete_snapshot_async(
        self,
        session_id: UUID,
        *,
        expected_revision: int,
    ) -> None:
        """Delete a snapshot without blocking the event loop."""

        await run_graph_work(
            partial(
                self.delete_snapshot,
                session_id,
                expected_revision=expected_revision,
            )
        )

    def delete_for_root_workflow(self, workflow_id: str) -> list[UUID]:
        """Delete every retained snapshot owned by one root workflow."""

        return self.delete_for_root_workflows([workflow_id])

    def delete_for_root_workflows(self, workflow_ids: list[str]) -> list[UUID]:
        """Delete retained snapshot trees for a set of removed root workflows."""

        target_ids = set(workflow_ids)
        if not target_ids:
            return []
        with self._lock:
            store = self._store()
            snapshots: dict[UUID, NestedWorkflowSnapshotResponse] = {}
            for path in self._snapshot_dir(store).glob("*.json"):
                try:
                    snapshot = self._read_path(path)
                except (OSError, ValueError):
                    # A malformed unrelated retained snapshot must not prevent
                    # cleanup for a workflow that has already been deleted.
                    continue
                snapshots[snapshot.session_id] = snapshot

            def root_id(snapshot: NestedWorkflowSnapshotResponse) -> str | None:
                visited: set[UUID] = set()
                current = snapshot
                while current.owner.kind == "nested":
                    parent_id = current.owner.session_id
                    if parent_id is None or parent_id in visited:
                        return None
                    visited.add(parent_id)
                    parent = snapshots.get(parent_id)
                    if parent is None:
                        return None
                    current = parent
                return current.owner.workflow_id

            removed = [
                session_id
                for session_id, snapshot in snapshots.items()
                if root_id(snapshot) in target_ids
            ]
            for session_id in removed:
                try:
                    self._path(store, session_id).unlink()
                except FileNotFoundError:
                    pass
            return removed

    def _find_snapshot(
        self,
        store: WorkflowStoreService,
        owner: NestedSnapshotOwner,
        parent_node_id: str,
    ) -> NestedWorkflowSnapshotResponse | None:
        for path in self._snapshot_dir(store).glob("*.json"):
            candidate = self._read_path(path)
            if candidate.owner == owner and candidate.parent_node_id == parent_node_id:
                return candidate
        return None

    def _root_validation_context_locked(
        self,
        store: WorkflowStoreService,
        owner: NestedSnapshotOwner,
    ) -> _RootValidationContext:
        workflow_id = self._root_workflow_id(store, owner)
        if workflow_id is None:
            return _RootValidationContext(
                workflow_id=None,
                identity_generation=None,
                storage_path=self._fallback_storage_path_provider(),
            )
        with store.workflow_mutation(workflow_id):
            store.get_workflow(workflow_id)
            return _RootValidationContext(
                workflow_id=workflow_id,
                identity_generation=store.workflow_generation(workflow_id),
                storage_path=store.get_storage_path(workflow_id),
            )

    @contextmanager
    def _root_validation_commit_locked(
        self,
        store: WorkflowStoreService,
        owner: NestedSnapshotOwner,
        expected: _RootValidationContext,
    ) -> Iterator[bool]:
        workflow_id = self._root_workflow_id(store, owner)
        if workflow_id != expected.workflow_id:
            yield False
            return
        if workflow_id is None:
            yield self._fallback_storage_path_provider() == expected.storage_path
            return

        assert expected.identity_generation is not None
        with store.workflow_mutation(workflow_id):
            store.ensure_workflow_generation(
                workflow_id,
                expected.identity_generation,
            )
            yield store.get_storage_path(workflow_id) == expected.storage_path

    def _dependent_session_ids(
        self,
        store: WorkflowStoreService,
        session_id: UUID,
    ) -> list[UUID]:
        dependents: list[UUID] = []
        for path in self._snapshot_dir(store).glob("*.json"):
            candidate = self._read_path(path)
            if candidate.owner.kind == "nested" and candidate.owner.session_id == session_id:
                dependents.append(candidate.session_id)
        return dependents

    def _root_workflow_id(
        self,
        store: WorkflowStoreService,
        owner: NestedSnapshotOwner,
    ) -> str | None:
        if owner.kind == "root":
            if owner.workflow_id is not None:
                store.get_workflow(owner.workflow_id)
            return owner.workflow_id

        assert owner.session_id is not None
        visited: set[UUID] = set()
        current_session_id = owner.session_id
        while True:
            if current_session_id in visited:
                raise ValueError("Nested snapshot ownership cycle")
            visited.add(current_session_id)
            parent = self._read(store, current_session_id)
            if parent.owner.kind == "root":
                if parent.owner.workflow_id is not None:
                    store.get_workflow(parent.owner.workflow_id)
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
        return NestedWorkflowSnapshotResponse.model_validate_json(path.read_text(encoding="utf-8"))

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

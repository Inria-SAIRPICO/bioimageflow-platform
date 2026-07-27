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
from urllib.parse import quote
from uuid import UUID

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedSnapshotOwner,
    NestedWorkflowSnapshotResponse,
)
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.models.workflow import validate_workflow_id
from bioimageflow_server.services.filesystem_durability import fsync_directory
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
class RootWorkflowSnapshotMove:
    """One durable root-workflow identity transition."""

    old_workflow_id: str
    old_identity_generation: int
    new_workflow_id: str
    new_identity_generation: int


@dataclass(frozen=True)
class _RootValidationContext:
    workflow_id: str | None
    identity_generation: int | None
    storage_path: Path | None


@dataclass(frozen=True)
class _SnapshotInventory:
    snapshots: dict[UUID, NestedWorkflowSnapshotResponse]
    paths: dict[UUID, Path]
    unreadable_session_ids: tuple[UUID, ...]
    discarded_paths: tuple[Path, ...]
    discarded_session_ids: tuple[UUID, ...]
    temporary_paths: tuple[Path, ...]


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
                store.ensure_workflow_mutations_available()
                owner = self._canonicalize_open_owner_locked(store, owner)
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
                    store.ensure_workflow_mutations_available()
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
                store.ensure_workflow_mutations_available()
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

    def has_open_at_or_below(self, workflow_id: str, workflow_path: list[str]) -> bool:
        """Return whether a durable editor owns the target or a descendant."""

        with self._lock:
            store = self._store()
            inventory = self._inventory_locked(store)
            snapshots = inventory.snapshots

            def root_and_path(
                snapshot: NestedWorkflowSnapshotResponse,
            ) -> tuple[str | None, list[str]]:
                path = [snapshot.parent_node_id]
                owner = snapshot.owner
                seen: set[UUID] = set()
                while owner.kind == "nested" and owner.session_id is not None:
                    if owner.session_id in seen:
                        return None, []
                    seen.add(owner.session_id)
                    parent = snapshots.get(owner.session_id)
                    if parent is None:
                        return None, []
                    path.insert(0, parent.parent_node_id)
                    owner = parent.owner
                return owner.workflow_id, path

            for snapshot in snapshots.values():
                root_id, path = root_and_path(snapshot)
                if root_id != workflow_id:
                    continue
                if path[: len(workflow_path)] == workflow_path:
                    return True
            return False

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
                store.ensure_workflow_mutations_available()
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
                    store.ensure_workflow_mutations_available()
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
                store.ensure_workflow_mutations_available()
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
            store.ensure_workflow_mutations_available()
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
            store.ensure_workflow_mutations_available()
            inventory = self._inventory_locked(store)

            removed = [
                session_id
                for session_id in inventory.snapshots
                if self._inventory_root_workflow_id(inventory, session_id) in target_ids
            ]
            for session_id in removed:
                try:
                    inventory.paths[session_id].unlink()
                except FileNotFoundError:
                    pass
            return removed

    def preflight_root_workflow_moves(self) -> None:
        """Reject a move before filesystem mutation if snapshot ownership is unreadable."""

        with self._lock:
            inventory = self._inventory_locked(self._store())
            self._ensure_move_inventory_is_readable(inventory)

    def move_root_workflows(
        self,
        moves: list[RootWorkflowSnapshotMove],
    ) -> list[UUID]:
        """Move retained root ownership without changing nested session identity."""

        if not moves:
            return []

        move_by_old_identity: dict[tuple[str, int], RootWorkflowSnapshotMove] = {}
        legacy_move_by_old_workflow: dict[str, RootWorkflowSnapshotMove] = {}
        for move in moves:
            key = (move.old_workflow_id, move.old_identity_generation)
            conflicting = move_by_old_identity.get(key)
            if conflicting is not None and conflicting != move:
                raise ValueError(
                    "Conflicting retained snapshot moves for "
                    f"{move.old_workflow_id!r} generation "
                    f"{move.old_identity_generation}"
                )
            move_by_old_identity[key] = move
            if move.old_identity_generation in (0, 1):
                conflicting_legacy = legacy_move_by_old_workflow.get(move.old_workflow_id)
                if conflicting_legacy is not None and conflicting_legacy != move:
                    raise ValueError(
                        "Conflicting generation-less retained snapshot moves for "
                        f"{move.old_workflow_id!r}"
                    )
                legacy_move_by_old_workflow[move.old_workflow_id] = move

        with self._lock:
            store = self._store()
            for move in move_by_old_identity.values():
                with store.workflow_mutation(move.new_workflow_id):
                    workflow = store.get_workflow(move.new_workflow_id)
                    if workflow.info.identity_generation != move.new_identity_generation:
                        store.ensure_workflow_generation(
                            move.new_workflow_id,
                            move.new_identity_generation,
                        )

            inventory = self._inventory_locked(store)
            self._ensure_move_inventory_is_readable(inventory)
            replacements: list[NestedWorkflowSnapshotResponse] = []
            moved_session_ids: list[UUID] = []
            for session_id, snapshot in inventory.snapshots.items():
                owner = snapshot.owner
                if owner.kind != "root" or owner.workflow_id is None:
                    continue
                move = (
                    legacy_move_by_old_workflow.get(owner.workflow_id)
                    if owner.identity_generation is None
                    else move_by_old_identity.get((owner.workflow_id, owner.identity_generation))
                )
                if move is None:
                    continue
                moved_owner = NestedSnapshotOwner(
                    kind="root",
                    canvas_id=self._canonical_root_canvas_id(move.new_workflow_id),
                    workflow_id=move.new_workflow_id,
                    identity_generation=move.new_identity_generation,
                )
                if moved_owner == owner:
                    continue
                replacements.append(snapshot.model_copy(update={"owner": moved_owner}))
                moved_session_ids.append(session_id)

            projected_snapshots = dict(inventory.snapshots)
            projected_snapshots.update({snapshot.session_id: snapshot for snapshot in replacements})
            losing_roots = self._canonical_root_collision_losers(
                inventory,
                projected_snapshots,
            )
            removed_session_ids = self._snapshot_descendant_closure(
                inventory,
                losing_roots,
            )
            replacements = [
                snapshot
                for snapshot in replacements
                if snapshot.session_id not in removed_session_ids
            ]
            self._write_many(store, replacements)
            for session_id in removed_session_ids:
                try:
                    inventory.paths[session_id].unlink()
                except FileNotFoundError:
                    pass
            if self._snapshot_dir(store).exists():
                # Reaffirm an already-applied replacement before a recovery
                # coordinator is allowed to clear its durable move journal.
                self._fsync_directory(self._snapshot_dir(store))
            return [
                session_id
                for session_id in moved_session_ids
                if session_id not in removed_session_ids
            ]

    def cleanup_orphaned_snapshots(self) -> list[UUID]:
        """Remove snapshots that cannot be safely recovered after startup."""

        store = self._store()
        with self._lock, store.workflow_structure_mutation():
            inventory = self._inventory_locked(store)
            workflow_generations: dict[str, int] = {}
            missing_workflow_ids: set[str] = set()
            uncertain_workflow_ids: set[str] = set()
            invalid_session_ids: set[UUID] = set()
            replacements: list[NestedWorkflowSnapshotResponse] = []

            for session_id, snapshot in inventory.snapshots.items():
                owner = snapshot.owner
                if owner.kind != "root":
                    continue
                workflow_id = owner.workflow_id
                if workflow_id is None:
                    invalid_session_ids.add(session_id)
                    continue
                try:
                    if validate_workflow_id(workflow_id) != workflow_id:
                        raise ValueError("Non-canonical retained root workflow identity")
                except ValueError:
                    invalid_session_ids.add(session_id)
                    continue
                if workflow_id in uncertain_workflow_ids:
                    continue
                if workflow_id in missing_workflow_ids:
                    invalid_session_ids.add(session_id)
                    continue
                current_generation = workflow_generations.get(workflow_id)
                if current_generation is None:
                    try:
                        workflow = store.get_workflow(workflow_id)
                    except FileNotFoundError:
                        missing_workflow_ids.add(workflow_id)
                        invalid_session_ids.add(session_id)
                        continue
                    except (OSError, ValueError):
                        uncertain_workflow_ids.add(workflow_id)
                        continue
                    current_generation = workflow.info.identity_generation
                    workflow_generations[workflow_id] = current_generation
                if owner.identity_generation is None:
                    if current_generation not in (0, 1):
                        invalid_session_ids.add(session_id)
                        continue
                elif owner.identity_generation != current_generation:
                    invalid_session_ids.add(session_id)
                    continue

                canonical_owner = NestedSnapshotOwner(
                    kind="root",
                    canvas_id=self._canonical_root_canvas_id(workflow_id),
                    workflow_id=workflow_id,
                    identity_generation=current_generation,
                )
                if canonical_owner != owner:
                    replacements.append(snapshot.model_copy(update={"owner": canonical_owner}))

            projected_snapshots = dict(inventory.snapshots)
            projected_snapshots.update({snapshot.session_id: snapshot for snapshot in replacements})
            collision_exclusions = set(invalid_session_ids)
            collision_exclusions.update(
                session_id
                for session_id, snapshot in projected_snapshots.items()
                if snapshot.owner.workflow_id in uncertain_workflow_ids
            )
            invalid_session_ids.update(
                self._canonical_root_collision_losers(
                    inventory,
                    projected_snapshots,
                    excluded_session_ids=collision_exclusions,
                )
            )

            visit_state: dict[UUID, int] = {}

            def has_valid_root(session_id: UUID) -> bool:
                if session_id in invalid_session_ids:
                    return False
                state = visit_state.get(session_id, 0)
                if state == 1:
                    invalid_session_ids.add(session_id)
                    return False
                if state == 2:
                    return session_id not in invalid_session_ids

                visit_state[session_id] = 1
                snapshot = inventory.snapshots[session_id]
                if snapshot.owner.kind == "root":
                    valid = session_id not in invalid_session_ids
                else:
                    parent_id = snapshot.owner.session_id
                    valid = parent_id is not None and (
                        parent_id in inventory.unreadable_session_ids
                        or (parent_id in inventory.snapshots and has_valid_root(parent_id))
                    )
                if not valid:
                    invalid_session_ids.add(session_id)
                visit_state[session_id] = 2
                return valid

            for session_id in inventory.snapshots:
                has_valid_root(session_id)

            replacements = [
                snapshot
                for snapshot in replacements
                if snapshot.session_id not in invalid_session_ids
            ]
            self._write_many(store, replacements)

            discarded_paths = {
                *inventory.discarded_paths,
                *inventory.temporary_paths,
                *(inventory.paths[session_id] for session_id in invalid_session_ids),
            }
            for path in sorted(discarded_paths):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass

            return sorted(
                {
                    *inventory.discarded_session_ids,
                    *invalid_session_ids,
                },
                key=str,
            )

    @staticmethod
    def _canonical_root_canvas_id(workflow_id: str) -> str:
        return f"workflow:{quote(workflow_id, safe='')}"

    @staticmethod
    def _snapshot_collision_rank(
        original: NestedWorkflowSnapshotResponse,
        projected: NestedWorkflowSnapshotResponse,
    ) -> tuple[datetime, int, bool, str]:
        try:
            updated_at = datetime.fromisoformat(projected.updated_at.replace("Z", "+00:00"))
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            else:
                updated_at = updated_at.astimezone(UTC)
        except ValueError:
            updated_at = datetime.min.replace(tzinfo=UTC)
        return (
            updated_at,
            projected.snapshot_revision,
            original.owner == projected.owner,
            str(projected.session_id),
        )

    def _canonical_root_collision_losers(
        self,
        inventory: _SnapshotInventory,
        projected_snapshots: dict[UUID, NestedWorkflowSnapshotResponse],
        *,
        excluded_session_ids: set[UUID] | None = None,
    ) -> set[UUID]:
        excluded = excluded_session_ids or set()
        canonical_groups: dict[
            tuple[str, str, int, str],
            list[UUID],
        ] = {}
        for session_id, snapshot in projected_snapshots.items():
            owner = snapshot.owner
            if (
                session_id in excluded
                or owner.kind != "root"
                or owner.canvas_id is None
                or owner.workflow_id is None
                or owner.identity_generation is None
            ):
                continue
            key = (
                owner.canvas_id,
                owner.workflow_id,
                owner.identity_generation,
                snapshot.parent_node_id,
            )
            canonical_groups.setdefault(key, []).append(session_id)

        losers: set[UUID] = set()
        for session_ids in canonical_groups.values():
            if len(session_ids) < 2:
                continue
            winner = max(
                session_ids,
                key=lambda session_id: self._snapshot_collision_rank(
                    inventory.snapshots[session_id],
                    projected_snapshots[session_id],
                ),
            )
            losers.update(session_id for session_id in session_ids if session_id != winner)
        return losers

    @staticmethod
    def _snapshot_descendant_closure(
        inventory: _SnapshotInventory,
        root_session_ids: set[UUID],
    ) -> set[UUID]:
        removed = set(root_session_ids)
        while True:
            descendants = {
                session_id
                for session_id, snapshot in inventory.snapshots.items()
                if snapshot.owner.kind == "nested" and snapshot.owner.session_id in removed
            }
            expanded = removed | descendants
            if expanded == removed:
                return removed
            removed = expanded

    @staticmethod
    def _ensure_move_inventory_is_readable(inventory: _SnapshotInventory) -> None:
        if inventory.unreadable_session_ids:
            unreadable = ", ".join(map(str, inventory.unreadable_session_ids))
            raise OSError(
                "Cannot move workflow identities while retained snapshots are unreadable: "
                f"{unreadable}"
            )

    def _canonicalize_open_owner_locked(
        self,
        store: WorkflowStoreService,
        owner: NestedSnapshotOwner,
    ) -> NestedSnapshotOwner:
        if owner.kind != "root" or owner.workflow_id is None:
            return owner
        with store.workflow_mutation(owner.workflow_id):
            workflow = store.get_workflow(owner.workflow_id)
            return NestedSnapshotOwner(
                kind="root",
                canvas_id=self._canonical_root_canvas_id(workflow.info.id),
                workflow_id=workflow.info.id,
                identity_generation=workflow.info.identity_generation,
            )

    def _inventory_locked(
        self,
        store: WorkflowStoreService,
    ) -> _SnapshotInventory:
        snapshot_dir = self._snapshot_dir(store)
        snapshots: dict[UUID, NestedWorkflowSnapshotResponse] = {}
        paths: dict[UUID, Path] = {}
        unreadable_session_ids: list[UUID] = []
        discarded_paths: list[Path] = []
        discarded_session_ids: list[UUID] = []
        temporary_paths: list[Path] = []
        if not snapshot_dir.exists():
            return _SnapshotInventory(
                snapshots=snapshots,
                paths=paths,
                unreadable_session_ids=(),
                discarded_paths=(),
                discarded_session_ids=(),
                temporary_paths=(),
            )

        for path in sorted(snapshot_dir.iterdir()):
            if not path.is_file():
                continue
            if path.suffix == ".tmp":
                temporary_paths.append(path)
                continue
            if path.suffix != ".json":
                continue
            try:
                filename_session_id = UUID(path.stem)
            except ValueError:
                discarded_paths.append(path)
                continue
            if path.name != f"{filename_session_id}.json":
                discarded_paths.append(path)
                discarded_session_ids.append(filename_session_id)
                continue
            try:
                snapshot = self._read_path(path)
            except OSError:
                unreadable_session_ids.append(filename_session_id)
                continue
            except ValueError:
                discarded_paths.append(path)
                discarded_session_ids.append(filename_session_id)
                continue
            if snapshot.session_id != filename_session_id:
                discarded_paths.append(path)
                discarded_session_ids.append(filename_session_id)
                continue
            snapshots[filename_session_id] = snapshot
            paths[filename_session_id] = path

        return _SnapshotInventory(
            snapshots=snapshots,
            paths=paths,
            unreadable_session_ids=tuple(unreadable_session_ids),
            discarded_paths=tuple(discarded_paths),
            discarded_session_ids=tuple(discarded_session_ids),
            temporary_paths=tuple(temporary_paths),
        )

    @staticmethod
    def _inventory_root_workflow_id(
        inventory: _SnapshotInventory,
        session_id: UUID,
    ) -> str | None:
        visited: set[UUID] = set()
        current_session_id = session_id
        while current_session_id not in visited:
            visited.add(current_session_id)
            snapshot = inventory.snapshots.get(current_session_id)
            if snapshot is None:
                return None
            if snapshot.owner.kind == "root":
                return snapshot.owner.workflow_id
            parent_id = snapshot.owner.session_id
            if parent_id is None:
                return None
            current_session_id = parent_id
        return None

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
            self._ensure_root_owner_is_current(store, owner)
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
                self._ensure_root_owner_is_current(store, parent.owner)
                return parent.owner.workflow_id
            assert parent.owner.session_id is not None
            current_session_id = parent.owner.session_id

    @staticmethod
    def _ensure_root_owner_is_current(
        store: WorkflowStoreService,
        owner: NestedSnapshotOwner,
    ) -> None:
        workflow_id = owner.workflow_id
        if workflow_id is None:
            return
        with store.workflow_mutation(workflow_id):
            workflow = store.get_workflow(workflow_id)
            current_generation = workflow.info.identity_generation
            if owner.identity_generation is None:
                if current_generation not in (0, 1):
                    raise FileNotFoundError(
                        f"Retained snapshot targets an obsolete generation of "
                        f"workflow '{workflow_id}'"
                    )
                return
            store.ensure_workflow_generation(workflow_id, owner.identity_generation)

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
        self._write_many(store, [snapshot])

    def _write_many(
        self,
        store: WorkflowStoreService,
        snapshots: list[NestedWorkflowSnapshotResponse],
    ) -> None:
        if not snapshots:
            return

        paths = [self._path(store, snapshot.session_id) for snapshot in snapshots]
        if len(set(paths)) != len(paths):
            raise ValueError("Cannot write the same retained snapshot more than once")
        originals = {path: path.read_bytes() if path.exists() else None for path in paths}
        staged: list[tuple[Path, Path]] = []
        try:
            for snapshot, path in zip(snapshots, paths, strict=True):
                staged.append((self._stage_snapshot(path, snapshot), path))
        except Exception:
            self._remove_staged_files(staged)
            raise

        replaced: list[Path] = []
        try:
            for temporary_path, path in staged:
                os.replace(temporary_path, path)
                replaced.append(path)
            self._fsync_directory(paths[0].parent)
        except Exception:
            self._remove_staged_files(staged)
            rollback_error: Exception | None = None
            for path in reversed(replaced):
                try:
                    original = originals[path]
                    if original is None:
                        path.unlink(missing_ok=True)
                    else:
                        self._replace_bytes(path, original)
                except Exception as error:
                    rollback_error = error
            try:
                self._fsync_directory(paths[0].parent)
            except Exception as error:
                rollback_error = error
            if rollback_error is not None:
                raise RuntimeError(
                    "Retained snapshot write failed and could not be rolled back"
                ) from rollback_error
            raise
        finally:
            self._remove_staged_files(staged)

    @staticmethod
    def _stage_snapshot(
        path: Path,
        snapshot: NestedWorkflowSnapshotResponse,
    ) -> Path:
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
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise
        return Path(tmp_name)

    @staticmethod
    def _replace_bytes(path: Path, contents: bytes) -> None:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.stem}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(contents)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        fsync_directory(path)

    @staticmethod
    def _remove_staged_files(staged: list[tuple[Path, Path]]) -> None:
        for temporary_path, _path in staged:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass

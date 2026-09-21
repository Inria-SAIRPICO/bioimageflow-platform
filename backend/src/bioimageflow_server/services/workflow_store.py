"""Filesystem-backed workflow persistence service."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import shutil
import tempfile
import threading
import zipfile
from io import BytesIO
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from bioimageflow_server.models.graph import GraphState, WorkflowNodeState
from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedWorkflowSnapshotResponse,
)
from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowDocument,
    WorkflowFile,
    WorkflowFolderDelete,
    WorkflowFolderInfo,
    WorkflowFormatNotice,
    WorkflowFormatStatus,
    WorkflowInfo,
    WorkflowImportResponse,
    WorkflowSaveBody,
    WorkflowUpdate,
    WorkspaceWorkflowMetadata,
    ViewingRequirementsManifest,
    validate_workflow_id,
)
from bioimageflow_server.models.workflow_draft import WorkflowDraftResponse
from bioimageflow_server.models.workflow_move_recovery import (
    WorkflowArtifactMove,
    WorkflowMoveJournal,
    WorkflowMoveKind,
    WorkflowMovePhase,
    WorkflowPromotionChildMove,
)
from bioimageflow_server.services.filesystem_durability import (
    fsync_directory as _fsync_directory,
    fsync_file as _fsync_file,
)
from bioimageflow_server.services.graph_translator import (
    _detect_missing_packages,
    _detect_missing_tools,
    graph_state_to_lib_dict,
    lib_dict_to_graph_state,
    rebind_lib_dict_versions,
)
from bioimageflow_server.services.workflow_artifacts import (
    OwnedWorkflowSources,
    capture_library_sources,
    capture_working_graph,
    canonical_json_bytes,
    artifact_hash,
    referenced_source_ids,
    rewrite_workspace_source_hashes,
    rewrite_workspace_source_ids,
)
from bioimageflow_server.services.workflow_containment import (
    validate_workflow_containment,
)
from bioimageflow_server.services.workflow_format import (
    migrate_legacy_workflow,
    normalize_legacy_workflow_document,
    normalize_legacy_workflow_draft,
    workflow_format_error,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_archive import (
    BioImageFlowWorkflowArchiveAdapter,
    safe_workflow_export_stem,
)


class WorkflowArchiveError(ValueError):
    """Raised when a workflow archive cannot be imported or exported."""


class WorkflowResultsBundleImportError(WorkflowArchiveError):
    """Raised when a results bundle is passed to the portable workflow importer."""


class WorkflowGenerationChangedError(FileNotFoundError):
    """Raised when a request targets an identity generation that was deleted."""

    def __init__(self, workflow_id: str) -> None:
        self.workflow_id = workflow_id
        super().__init__(
            f"Workflow '{workflow_id}' was deleted or replaced while the request waited"
        )


class WorkflowIdentityGenerationConflictError(ValueError):
    """Raised when a caller targets a stale durable workflow identity."""

    def __init__(self, workflow_id: str, expected: int, current: int) -> None:
        self.workflow_id = workflow_id
        self.expected = expected
        self.current = current
        super().__init__(
            f"Workflow '{workflow_id}' generation is {current}, not expected {expected}"
        )


class WorkflowGenerationLedgerError(RuntimeError):
    """Raised when durable workflow identity generations cannot be trusted."""


class WorkflowMoveRecoveryError(RuntimeError):
    """Raised when an interrupted workflow move cannot be trusted or completed."""


class WorkflowFormatUpdateRequiredError(RuntimeError):
    """Raised when a workflow is intentionally deferred in an older format."""

    def __init__(self, workflow_id: str) -> None:
        self.workflow_id = workflow_id
        super().__init__(f"Workflow '{workflow_id}' requires a format update")


class WorkflowFormatPlanStaleError(RuntimeError):
    """Raised when confirmation no longer matches the previewed source bytes."""


@dataclass(frozen=True)
class WorkflowIdentityMovePlan:
    """One root workflow identity move captured before filesystem mutation."""

    old_workflow_id: str
    old_identity_generation: int
    new_workflow_id: str


@dataclass(frozen=True)
class WorkflowTemplate:
    """Validated workflow document and local tool files to install together."""

    workflow_id: str
    document: WorkflowDocument
    tool_files: dict[str, bytes]


_WORKFLOW_GENERATION_LEDGER_VERSION = 1
_WORKFLOW_GENERATION_LEDGER_NAME = "workflow-identity-generations.json"
_WORKFLOW_MOVE_JOURNAL_NAME = "workflow-move-journal.json"
_SCHEMA_V2_MIGRATION_JOURNAL_NAME = "schema-v2-migration.json"
logger = logging.getLogger(__name__)


def _schema_v2_json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _workflow_format_plan_directory(plan_id: str) -> str:
    if re.fullmatch(r"sha256:[0-9a-f]{64}", plan_id) is None:
        raise WorkflowMoveRecoveryError("Workflow-format plan ID is invalid")
    return plan_id.replace(":", "-")


class _WorkflowWorkspaceCoordination:
    """Process-level locks and generations shared by one canonical workspace."""

    def __init__(self, generations: dict[str, int]) -> None:
        self.workflow_locks: dict[str, threading.RLock] = {}
        self.workflow_locks_guard = threading.Lock()
        self.structure_lock = threading.RLock()
        self.generations = generations
        self.generations_guard = threading.Lock()


_WORKFLOW_COORDINATIONS: dict[
    tuple[Path, Path],
    _WorkflowWorkspaceCoordination,
] = {}
_WORKFLOW_COORDINATIONS_GUARD = threading.Lock()


class WorkflowArchiveAdapter(Protocol):
    """Small boundary around BioImageFlow archive APIs."""

    def export_archive(
        self,
        workflow_data: dict[str, Any],
        archive_path: Path,
        *,
        storage_path: Path,
    ) -> None: ...

    def read_archive(
        self,
        archive_path: Path,
        *,
        extract_to: Path | None = None,
        storage_path: Path,
    ) -> dict[str, Any]: ...

    def inspect_viewing_requirements(self, archive_path: Path) -> dict[str, Any]: ...


def _identity_locked(method: Any) -> Any:
    """Serialize one workflow identity across saved and draft mutations."""

    @wraps(method)
    def wrapped(self: "WorkflowStoreService", name: str, *args: Any, **kwargs: Any) -> Any:
        with self.workflow_mutation(name):
            return method(self, name, *args, **kwargs)

    return wrapped


def _ensure_directory_durable(path: Path, *, anchor: Path) -> None:
    """Create and reaffirm a directory chain through one known authority root."""

    try:
        path.relative_to(anchor)
    except ValueError as exc:
        raise ValueError(f"Directory {path} is outside durable anchor {anchor}") from exc
    path.mkdir(parents=True, exist_ok=True)
    current = path
    while True:
        _fsync_directory(current)
        if current == anchor:
            _fsync_directory(anchor.parent)
            return
        current = current.parent


def _prepared_workflow_draft_identity(
    workflow_dir: Path,
    workflow_id: str,
) -> tuple[Path, dict[str, Any], bool] | None:
    """Load and validate the path-authoritative form of an existing draft."""

    draft_path = workflow_dir / ".bioimageflow" / "draft.json"
    if not draft_path.exists():
        return None

    with draft_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"Draft file {draft_path} must contain a JSON object")

    identity_changed = raw.get("workflow_id") != workflow_id
    normalized = {**raw, "workflow_id": workflow_id} if identity_changed else raw
    WorkflowDraftResponse.model_validate(normalized)
    return draft_path, normalized, identity_changed


def normalize_workflow_draft_identity(
    workflow_dir: Path,
    workflow_id: str,
) -> dict[str, Any] | None:
    """Return an existing draft, repairing its path-derived identity if needed."""

    prepared = _prepared_workflow_draft_identity(workflow_dir, workflow_id)
    if prepared is None:
        return None
    draft_path, normalized, identity_changed = prepared
    if not identity_changed:
        return normalized
    fd, tmp_name = tempfile.mkstemp(
        dir=str(draft_path.parent),
        prefix=f".{draft_path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, draft_path)
        _fsync_directory(draft_path.parent)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    return normalized


class WorkflowStoreService:
    """Manage workflow JSON files under one root directory."""

    def __init__(
        self,
        root_dir: Path,
        tool_registry: ToolRegistryService,
        *,
        archive_adapter: WorkflowArchiveAdapter | None = None,
    ) -> None:
        self.root_dir = self._normalize_storage_path(root_dir)
        self.workspace_dir = (
            self.root_dir.parent if self.root_dir.name == "workflows" else self.root_dir
        )
        self.tool_registry = tool_registry
        self.archive_adapter = archive_adapter or BioImageFlowWorkflowArchiveAdapter()
        self._workflow_format_notices: list[WorkflowFormatNotice] = []
        self._workflow_generation_ledger_path = (
            self.workspace_dir / ".bioimageflow" / _WORKFLOW_GENERATION_LEDGER_NAME
        )
        self._workflow_move_journal_path = (
            self.workspace_dir / ".bioimageflow" / _WORKFLOW_MOVE_JOURNAL_NAME
        )
        self._schema_v2_migration_journal_path = (
            self.workspace_dir / ".bioimageflow" / _SCHEMA_V2_MIGRATION_JOURNAL_NAME
        )
        coordination_key = (
            self.root_dir.resolve(strict=False),
            self._workflow_generation_ledger_path.resolve(strict=False),
        )
        with _WORKFLOW_COORDINATIONS_GUARD:
            coordination = _WORKFLOW_COORDINATIONS.get(coordination_key)
            if coordination is None:
                coordination = _WorkflowWorkspaceCoordination(
                    self._load_workflow_generation_ledger()
                )
                _WORKFLOW_COORDINATIONS[coordination_key] = coordination
        self._workflow_coordination = coordination
        self._workflow_locks = coordination.workflow_locks
        self._workflow_locks_guard = coordination.workflow_locks_guard
        self._workflow_structure_lock = coordination.structure_lock
        self._workflow_generations = coordination.generations
        self._workflow_generations_guard = coordination.generations_guard
        with self._workflow_generations_guard:
            persisted = self._load_workflow_generation_ledger()
            for name, generation in persisted.items():
                if generation > self._workflow_generations.get(name, 0):
                    self._workflow_generations[name] = generation

    @contextmanager
    def workflow_mutation(self, name: str) -> Iterator[None]:
        """Hold the shared mutation lock for a normalized workflow identity."""

        with self.workflow_mutations([name]):
            yield

    @contextmanager
    def workflow_mutations(self, names: list[str]) -> Iterator[None]:
        """Fence and lock identities in a stable order to avoid stale writes."""

        safe_names = sorted({self._validate_name(name) for name in names})
        expected_generations = self._capture_workflow_generations(safe_names)
        with self._workflow_identity_locks(safe_names):
            self._ensure_workflow_generations_current(expected_generations)
            yield

    @contextmanager
    def workflow_structural_mutations(self, names: list[str]) -> Iterator[None]:
        """Capture generations before waiting on the workspace structure lock."""

        safe_names = sorted({self._validate_name(name) for name in names})
        expected_generations = self._capture_workflow_generations(safe_names)
        with self._workflow_structure_lock, self._workflow_identity_locks(safe_names):
            self._ensure_workflow_generations_current(expected_generations)
            yield

    @contextmanager
    def _workflow_identity_locks(self, safe_names: list[str]) -> Iterator[None]:
        with self._workflow_locks_guard:
            locks: list[threading.RLock] = []
            for safe_name in safe_names:
                lock = self._workflow_locks.get(safe_name)
                if lock is None:
                    lock = threading.RLock()
                    self._workflow_locks[safe_name] = lock
                locks.append(lock)
        with ExitStack() as stack:
            for lock in locks:
                stack.enter_context(lock)
            yield

    def _capture_workflow_generations(self, names: list[str]) -> dict[str, int]:
        with self._workflow_generations_guard:
            return {name: self._workflow_generations.get(name, 0) for name in names}

    def _ensure_workflow_generations_current(
        self,
        expected: dict[str, int],
    ) -> None:
        with self._workflow_generations_guard:
            for name, generation in expected.items():
                if self._workflow_generations.get(name, 0) != generation:
                    raise WorkflowGenerationChangedError(name)

    def _load_workflow_generation_ledger(self) -> dict[str, int]:
        path = self._workflow_generation_ledger_path
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowGenerationLedgerError(
                f"Cannot read workflow identity generation ledger: {path}"
            ) from exc
        if (
            not isinstance(raw, dict)
            or set(raw) != {"version", "generations"}
            or isinstance(raw.get("version"), bool)
            or raw.get("version") != _WORKFLOW_GENERATION_LEDGER_VERSION
        ):
            raise WorkflowGenerationLedgerError(
                f"Invalid workflow identity generation ledger: {path}"
            )
        raw_generations = raw.get("generations")
        if not isinstance(raw_generations, dict):
            raise WorkflowGenerationLedgerError(
                f"Invalid workflow identity generation ledger: {path}"
            )
        generations: dict[str, int] = {}
        for raw_name, raw_generation in raw_generations.items():
            if not isinstance(raw_name, str):
                raise WorkflowGenerationLedgerError(
                    f"Invalid workflow identity in generation ledger: {path}"
                )
            try:
                name = validate_workflow_id(raw_name)
            except ValueError as exc:
                raise WorkflowGenerationLedgerError(
                    f"Invalid workflow identity in generation ledger: {path}"
                ) from exc
            if name != raw_name:
                raise WorkflowGenerationLedgerError(
                    f"Non-canonical workflow identity in generation ledger: {path}"
                )
            if (
                isinstance(raw_generation, bool)
                or not isinstance(raw_generation, int)
                or raw_generation < 0
            ):
                raise WorkflowGenerationLedgerError(
                    f"Invalid workflow generation for '{name}' in ledger: {path}"
                )
            generations[name] = raw_generation
        return generations

    def _write_workflow_generation_ledger(self, generations: dict[str, int]) -> None:
        path = self._workflow_generation_ledger_path
        self._ensure_directory_durable(path.parent)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.stem}.",
            suffix=".tmp.json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "version": _WORKFLOW_GENERATION_LEDGER_VERSION,
                        "generations": dict(sorted(generations.items())),
                    },
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
            self._fsync_directory(path.parent)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def _reserve_workflow_generations(self, names: list[str]) -> dict[str, int]:
        """Persist the next generations before mutating workflow identities."""

        safe_names = sorted({self._validate_name(name) for name in names})
        if not safe_names:
            return {}
        with self._workflow_generations_guard:
            persisted = self._load_workflow_generation_ledger()
            updated = dict(self._workflow_generations)
            for name, generation in persisted.items():
                if generation > updated.get(name, 0):
                    updated[name] = generation
            for name in safe_names:
                updated[name] = updated.get(name, 0) + 1
            self._write_workflow_generation_ledger(updated)
            self._workflow_generations.clear()
            self._workflow_generations.update(updated)
            return {name: updated[name] for name in safe_names}

    def workflow_generation(self, name: str) -> int:
        """Capture the durable generation for a workflow identity."""

        safe_name = self._validate_name(name)
        return self._capture_workflow_generations([safe_name])[safe_name]

    def ensure_workflow_generation(self, name: str, expected: int) -> None:
        """Reject work that began before the identity's latest replacement."""

        safe_name = self._validate_name(name)
        self._ensure_workflow_generations_current({safe_name: expected})

    def pending_workflow_move(self) -> WorkflowMoveJournal | None:
        """Return the exclusive durable move journal, rejecting untrusted records."""

        path = self._workflow_move_journal_path
        if not path.exists():
            return None
        try:
            journal = WorkflowMoveJournal.model_validate_json(path.read_text(encoding="utf-8"))
            self._validate_workflow_move_journal_authority(journal)
        except (OSError, ValidationError, ValueError) as exc:
            raise WorkflowMoveRecoveryError(
                f"Cannot trust pending workflow move journal: {path}"
            ) from exc
        return journal

    def ensure_workflow_mutations_available(
        self,
        *,
        move_operation_id: UUID | None = None,
    ) -> None:
        """Fence ordinary writes while an interrupted identity move is pending."""

        pending = self.pending_workflow_move()
        if pending is None:
            if move_operation_id is not None:
                raise WorkflowMoveRecoveryError(
                    f"Workflow move journal {move_operation_id} does not exist"
                )
            return
        if move_operation_id != pending.operation_id:
            raise WorkflowMoveRecoveryError(
                f"Workflow move {pending.operation_id} must recover before workspace mutation"
            )

    def _require_prepared_workflow_move(
        self,
        operation_id: UUID | None,
        *,
        operation_kind: WorkflowMoveKind,
        source_path: str,
        destination_path: str,
    ) -> WorkflowMoveJournal:
        if operation_id is None:
            raise WorkflowMoveRecoveryError(
                f"{operation_kind} requires a prepared workflow move journal"
            )
        self.ensure_workflow_mutations_available(move_operation_id=operation_id)
        journal = self._required_workflow_move(operation_id)
        if (
            journal.phase != "prepared"
            or journal.operation_kind != operation_kind
            or journal.source_path != source_path
            or journal.destination_path != destination_path
        ):
            raise WorkflowMoveRecoveryError(
                f"Workflow move {operation_id} does not authorize "
                f"{source_path!r} -> {destination_path!r}"
            )
        return journal

    def _validate_prepared_move_execution(
        self,
        journal: WorkflowMoveJournal,
        moves: list[tuple[str, str]],
        *,
        patches: dict[str, WorkflowUpdate] | None = None,
    ) -> None:
        """Prove the live executor inputs still equal the recorded prepared intent."""

        if not self._workflow_move_is_unstarted(journal):
            raise WorkflowMoveRecoveryError(
                f"Workflow move {journal.operation_id} already crossed its commit boundary"
            )
        recorded_moves = [
            (move.source_workflow_id, move.destination_workflow_id) for move in journal.moves
        ]
        if recorded_moves != moves:
            raise WorkflowMoveRecoveryError(
                f"Workflow move {journal.operation_id} does not match the current workflow tree"
            )
        generations = {
            identity: generation
            for move in journal.moves
            for identity, generation in (
                (move.source_workflow_id, move.source_generation_before),
                (move.destination_workflow_id, move.destination_generation_before),
            )
        }
        expected_artifacts = [
            self._prepare_workflow_artifact_move(
                old_name,
                new_name,
                generations,
                patch=(patches or {}).get(old_name),
            )
            for old_name, new_name in moves
        ]
        if expected_artifacts != journal.moves:
            raise WorkflowMoveRecoveryError(
                f"Workflow move {journal.operation_id} metadata no longer matches its journal"
            )

    def mark_workflow_move_phase(
        self,
        operation_id: UUID,
        phase: WorkflowMovePhase,
    ) -> None:
        """Durably advance one journal without permitting skips or reversal."""

        with self.workflow_structure_mutation():
            journal = self._required_workflow_move(operation_id)
            phase_order: dict[WorkflowMovePhase, int] = {
                "prepared": 0,
                "artifacts_rewritten": 1,
                "snapshots_rewritten": 2,
                "preferences_rewritten": 3,
            }
            current_index = phase_order[journal.phase]
            requested_index = phase_order[phase]
            if requested_index == current_index:
                return
            if requested_index != current_index + 1:
                raise WorkflowMoveRecoveryError(
                    f"Cannot advance workflow move {operation_id} from "
                    f"{journal.phase!r} to {phase!r}"
                )
            self._write_workflow_move_journal(journal.model_copy(update={"phase": phase}))

    def discard_workflow_move_if_unstarted(self, operation_id: UUID) -> None:
        """Discard a prepared record only while every durable artifact is untouched."""

        with self.workflow_structure_mutation():
            journal = self._required_workflow_move(operation_id)
            if journal.phase != "prepared" or not self._workflow_move_is_unstarted(journal):
                raise WorkflowMoveRecoveryError(
                    f"Workflow move {operation_id} has durable mutations and must recover"
                )
            self._remove_workflow_move_journal()

    def recover_pending_workflow_move(self) -> WorkflowMoveJournal | None:
        """Forward-complete all non-snapshot artifacts for an interrupted move."""

        journal = self.pending_workflow_move()
        if journal is None:
            return None
        workflow_ids = [
            workflow_id
            for move in journal.moves
            for workflow_id in (
                move.source_workflow_id,
                move.destination_workflow_id,
            )
        ]
        with self.workflow_structure_mutation(), self.workflow_mutations(workflow_ids):
            current = self._required_workflow_move(journal.operation_id)
            try:
                if self._abandon_uncommitted_workflow_move(current):
                    self._remove_workflow_move_journal()
                    return None
                self._preflight_workflow_move_recovery(current)
                self._recover_workflow_move_generations(current)
                self._recover_workflow_move_paths(current)
                self._recover_workflow_move_documents(current)
            except WorkflowMoveRecoveryError:
                raise
            except Exception as exc:
                raise WorkflowMoveRecoveryError(
                    f"Could not forward-complete workflow move {current.operation_id}"
                ) from exc

            if current.phase == "prepared":
                current = current.model_copy(update={"phase": "artifacts_rewritten"})
                self._write_workflow_move_journal(current)
            return current

    def complete_workflow_move(self, operation_id: UUID) -> None:
        """Remove a move journal after snapshots and viewer preferences commit."""

        with self.workflow_structure_mutation():
            journal = self._required_workflow_move(operation_id)
            if journal.phase != "preferences_rewritten":
                raise WorkflowMoveRecoveryError(
                    f"Workflow move {operation_id} cannot complete from phase {journal.phase!r}"
                )
            self._remove_workflow_move_journal()

    def _required_workflow_move(self, operation_id: UUID) -> WorkflowMoveJournal:
        journal = self.pending_workflow_move()
        if journal is None:
            raise WorkflowMoveRecoveryError(f"Workflow move journal {operation_id} does not exist")
        if journal.operation_id != operation_id:
            raise WorkflowMoveRecoveryError(
                f"Pending workflow move is {journal.operation_id}, not {operation_id}"
            )
        return journal

    def _write_new_workflow_move_journal(self, journal: WorkflowMoveJournal) -> None:
        if self._workflow_move_journal_path.exists():
            pending = self.pending_workflow_move()
            assert pending is not None
            raise WorkflowMoveRecoveryError(
                f"Workflow move {pending.operation_id} must complete before another move"
            )
        self._write_workflow_move_journal(journal)

    def _write_workflow_move_journal(self, journal: WorkflowMoveJournal) -> None:
        path = self._workflow_move_journal_path
        self._ensure_directory_durable(path.parent)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.stem}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(journal.model_dump(mode="json"), handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
            self._fsync_directory(path.parent)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def _remove_workflow_move_journal(self) -> None:
        try:
            self._workflow_move_journal_path.unlink()
        except FileNotFoundError:
            return
        self._fsync_directory(self._workflow_move_journal_path.parent)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        _fsync_directory(path)

    @staticmethod
    def _fsync_file(path: Path) -> None:
        _fsync_file(path)

    def _ensure_directory_durable(self, path: Path) -> None:
        anchors = (
            self.root_dir,
            self.workspace_dir,
        )
        anchor = next(
            (candidate for candidate in anchors if path.is_relative_to(candidate)),
            path,
        )
        _ensure_directory_durable(path, anchor=anchor)

    def _validate_workflow_move_journal_authority(
        self,
        journal: WorkflowMoveJournal,
    ) -> None:
        if journal.operation_kind == "folder_rename":
            source_prefix = f"{journal.source_path}/"
            destination_prefix = f"{journal.destination_path}/"
            for move in journal.moves:
                if not move.source_workflow_id.startswith(source_prefix):
                    raise ValueError("Folder move source is outside the recorded folder")
                suffix = move.source_workflow_id[len(source_prefix) :]
                if move.destination_workflow_id != f"{destination_prefix}{suffix}":
                    raise ValueError("Folder move destination does not preserve its relative id")
        elif journal.operation_kind == "folder_promotion":
            source_prefix = f"{journal.source_path}/"
            destination_prefix = f"{journal.destination_path}/" if journal.destination_path else ""
            for move in journal.moves:
                if not move.source_workflow_id.startswith(source_prefix):
                    raise ValueError("Promoted workflow is outside the removed folder")
                suffix = move.source_workflow_id[len(source_prefix) :]
                if move.destination_workflow_id != f"{destination_prefix}{suffix}":
                    raise ValueError("Promoted workflow does not preserve its relative id")

    def _workflow_move_is_unstarted(self, journal: WorkflowMoveJournal) -> bool:
        before, _ = self._workflow_move_generation_states(journal)
        try:
            persisted = self._load_workflow_generation_ledger()
        except WorkflowGenerationLedgerError as exc:
            raise WorkflowMoveRecoveryError(
                "Cannot discard a move while workflow generations are unreadable"
            ) from exc
        if any(persisted.get(name, 0) != generation for name, generation in before.items()):
            return False

        if journal.operation_kind == "folder_promotion":
            source_folder = self._journal_workflow_path(journal.source_path)
            if not source_folder.exists():
                return False
            if not self._promotion_source_inventory_is_exact(journal):
                return False
            for child in journal.promotion_children:
                source = self._journal_workflow_path(child.source_relative_path)
                destination = self._journal_workflow_path(child.destination_relative_path)
                if not source.exists() or destination.exists():
                    return False
        else:
            source = self._journal_workflow_path(journal.source_path)
            destination = self._journal_workflow_path(journal.destination_path)
            if not source.exists() or destination.exists():
                return False

        return True

    def _preflight_workflow_move_recovery(self, journal: WorkflowMoveJournal) -> None:
        before, after = self._workflow_move_generation_states(journal)
        persisted = self._load_workflow_generation_ledger()
        if before:
            before_matches = all(
                persisted.get(name, 0) == generation for name, generation in before.items()
            )
            after_matches = all(
                persisted.get(name, 0) == generation for name, generation in after.items()
            )
            if not before_matches and not after_matches:
                raise WorkflowMoveRecoveryError(
                    "Workflow move generations are mixed or outside the recorded transition"
                )

        if journal.operation_kind == "folder_promotion":
            if not self._promotion_source_inventory_is_exact(journal):
                raise WorkflowMoveRecoveryError(
                    "Promotion source folder contains an unrecorded child"
                )
            for child in journal.promotion_children:
                source_exists = self._journal_workflow_path(child.source_relative_path).exists()
                destination_exists = self._journal_workflow_path(
                    child.destination_relative_path
                ).exists()
                if source_exists == destination_exists:
                    raise WorkflowMoveRecoveryError(
                        "Promotion recovery requires exactly one child path for "
                        f"{child.source_relative_path}"
                    )
        else:
            source_exists = self._journal_workflow_path(journal.source_path).exists()
            destination_exists = self._journal_workflow_path(journal.destination_path).exists()
            if source_exists == destination_exists:
                raise WorkflowMoveRecoveryError(
                    "Move recovery requires exactly one source/destination path: "
                    f"{journal.source_path} -> {journal.destination_path}"
                )

        for move in journal.moves:
            source_document = self._path_for(move.source_workflow_id)
            destination_document = self._path_for(move.destination_workflow_id)
            if source_document.exists() == destination_document.exists():
                raise WorkflowMoveRecoveryError(
                    "Move recovery requires exactly one workflow document for "
                    f"{move.source_workflow_id} -> {move.destination_workflow_id}"
                )
            current_document = source_document if source_document.exists() else destination_document
            try:
                raw = json.loads(current_document.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("Workflow document must contain a JSON object")
                _prepared_workflow_draft_identity(
                    current_document.parent,
                    move.destination_workflow_id,
                )
            except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
                raise WorkflowMoveRecoveryError(
                    f"Cannot trust workflow artifacts at {current_document.parent}"
                ) from exc

    def _promotion_source_inventory_is_exact(
        self,
        journal: WorkflowMoveJournal,
    ) -> bool:
        source_folder = self._journal_workflow_path(journal.source_path)
        actual = (
            {child.relative_to(self.root_dir).as_posix() for child in source_folder.iterdir()}
            if source_folder.exists()
            else set()
        )
        expected = {
            child.source_relative_path
            for child in journal.promotion_children
            if self._journal_workflow_path(child.source_relative_path).exists()
        }
        return actual == expected

    def _abandon_uncommitted_workflow_move(self, journal: WorkflowMoveJournal) -> bool:
        before, after = self._workflow_move_generation_states(journal)
        if not before:
            unstarted = self._workflow_move_is_unstarted(journal)
            if unstarted and journal.phase != "prepared":
                raise WorkflowMoveRecoveryError(
                    "Workflow move phase claims committed artifacts but topology is untouched"
                )
            return unstarted

        persisted = self._load_workflow_generation_ledger()
        before_matches = all(
            persisted.get(name, 0) == generation for name, generation in before.items()
        )
        after_matches = all(
            persisted.get(name, 0) == generation for name, generation in after.items()
        )
        if after_matches:
            return False
        if not before_matches:
            raise WorkflowMoveRecoveryError(
                "Workflow move generations are mixed or outside the recorded transition"
            )
        if not self._workflow_move_is_unstarted(journal):
            raise WorkflowMoveRecoveryError(
                "Workflow move artifacts changed before its generation commit point"
            )
        if journal.phase != "prepared":
            raise WorkflowMoveRecoveryError(
                "Workflow move phase claims committed artifacts but generations are untouched"
            )
        return True

    @staticmethod
    def _workflow_move_generation_states(
        journal: WorkflowMoveJournal,
    ) -> tuple[dict[str, int], dict[str, int]]:
        before: dict[str, int] = {}
        after: dict[str, int] = {}
        for move in journal.moves:
            before[move.source_workflow_id] = move.source_generation_before
            after[move.source_workflow_id] = move.source_generation_after
            before[move.destination_workflow_id] = move.destination_generation_before
            after[move.destination_workflow_id] = move.destination_generation_after
        return before, after

    def _recover_workflow_move_generations(self, journal: WorkflowMoveJournal) -> None:
        before, after = self._workflow_move_generation_states(journal)
        if not before:
            return
        with self._workflow_generations_guard:
            persisted = self._load_workflow_generation_ledger()
            before_matches = all(
                persisted.get(name, 0) == generation for name, generation in before.items()
            )
            after_matches = all(
                persisted.get(name, 0) == generation for name, generation in after.items()
            )
            if not before_matches and not after_matches:
                actual = {name: persisted.get(name, 0) for name in before}
                raise WorkflowMoveRecoveryError(
                    "Workflow move generation state is neither its exact prepared nor "
                    f"committed value: {actual}"
                )

            if before_matches:
                updated = dict(persisted)
                for name, generation in self._workflow_generations.items():
                    if generation > updated.get(name, 0):
                        updated[name] = generation
                updated.update(after)
                self._write_workflow_generation_ledger(updated)
                persisted = updated

            self._fsync_file(self._workflow_generation_ledger_path)
            self._fsync_directory(self._workflow_generation_ledger_path.parent)

            for name, generation in persisted.items():
                if generation > self._workflow_generations.get(name, 0):
                    self._workflow_generations[name] = generation
            for name, generation in after.items():
                self._workflow_generations[name] = generation

    def _recover_workflow_move_paths(self, journal: WorkflowMoveJournal) -> None:
        if journal.operation_kind == "folder_promotion":
            for child in journal.promotion_children:
                self._recover_one_workflow_move_path(
                    self._journal_workflow_path(child.source_relative_path),
                    self._journal_workflow_path(child.destination_relative_path),
                )
            source_folder = self._journal_workflow_path(journal.source_path)
            if source_folder.exists():
                try:
                    source_folder.rmdir()
                except OSError as exc:
                    raise WorkflowMoveRecoveryError(
                        f"Promoted source folder still contains unrecorded artifacts: "
                        f"{source_folder}"
                    ) from exc
            self._fsync_directory(source_folder.parent)
            return

        self._recover_one_workflow_move_path(
            self._journal_workflow_path(journal.source_path),
            self._journal_workflow_path(journal.destination_path),
        )

    def _recover_one_workflow_move_path(self, source: Path, destination: Path) -> None:
        source_exists = source.exists()
        destination_exists = destination.exists()
        if source_exists and destination_exists:
            raise WorkflowMoveRecoveryError(
                f"Both workflow move paths exist: {source} and {destination}"
            )
        if not source_exists and not destination_exists:
            raise WorkflowMoveRecoveryError(
                f"Both workflow move paths are missing: {source} and {destination}"
            )
        if source_exists:
            self._ensure_directory_durable(destination.parent)
            source.rename(destination)
        if source.parent.exists():
            self._fsync_directory(source.parent)
        self._fsync_directory(destination.parent)

    def _recover_workflow_move_documents(self, journal: WorkflowMoveJournal) -> None:
        for move in journal.moves:
            destination = self._workflow_dir(move.destination_workflow_id)
            normalize_workflow_draft_identity(
                destination,
                move.destination_workflow_id,
            )
            draft_path = destination / ".bioimageflow" / "draft.json"
            if draft_path.exists():
                self._fsync_file(draft_path)
                self._fsync_directory(draft_path.parent)
            raw = self._read_raw(move.destination_workflow_id)
            recovered = cast(dict[str, Any], json.loads(json.dumps(raw)))
            recovered["metadata"] = json.loads(json.dumps(move.target_metadata))
            recovered_graph = GraphState.model_validate(recovered["graph"]).model_copy(
                update={"display_name": move.target_display_name}
            )
            recovered["graph"] = recovered_graph.model_dump(mode="json", by_alias=True)
            if recovered != raw:
                self._write_raw(move.destination_workflow_id, recovered)
            workflow_path = self._path_for(move.destination_workflow_id)
            self._fsync_file(workflow_path)
            self._fsync_directory(workflow_path.parent)

    def _journal_workflow_path(self, relative_path: str) -> Path:
        if relative_path == "":
            return self.root_dir
        return self.root_dir.joinpath(*relative_path.split("/"))

    @contextmanager
    def workflow_structure_mutation(self) -> Iterator[None]:
        """Serialize operations that change the workspace workflow tree."""

        with self._workflow_structure_lock:
            yield

    @staticmethod
    def _normalize_storage_path(path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if candidate.is_absolute():
            return candidate
        return Path.cwd() / candidate

    def _validate_name(self, name: str) -> str:
        return validate_workflow_id(name)

    def _leaf_name(self, name: str) -> str:
        return self._validate_name(name).split("/")[-1]

    def _folder_name(self, name: str) -> str:
        parts = self._validate_name(name).split("/")
        return "/".join(parts[:-1])

    def _path_for(self, name: str) -> Path:
        safe_name = self._validate_name(name)
        return self._workflow_dir(safe_name) / "workflow.json"

    def _workflow_dir(self, name: str) -> Path:
        return self.root_dir.joinpath(*self._validate_name(name).split("/"))

    def _workflow_tools_dir(self, name: str) -> Path:
        return self._workflow_dir(name) / "tools"

    def workflow_dir(self, name: str) -> Path:
        return self._workflow_dir(name)

    def workflow_tools_dir(self, name: str) -> Path:
        return self._workflow_tools_dir(name)

    def has_workflow_collision(self, name: str) -> bool:
        """Return whether a workflow identity blocks creation."""

        return self._has_name_collision(name)

    def read_workflow_document(self, name: str) -> WorkflowDocument:
        """Read the canonical persisted document for provenance checks."""

        with self.workflow_mutation(name):
            self._existing_path_for(name)
            return WorkflowDocument.model_validate(self._read_raw(name))

    def _ensure_workflow_layout(self, name: str) -> None:
        self._ensure_directory_durable(self._workflow_tools_dir(name))

    def _existing_path_for(self, name: str) -> Path:
        path = self._path_for(name)
        if path.exists():
            return path
        raise FileNotFoundError(name)

    def _has_name_collision(self, name: str) -> bool:
        return self._path_for(name).exists() or self._workflow_dir(name).exists()

    def _workflow_names_under_folder(self, folder: Path) -> list[str]:
        if not folder.exists():
            return []
        names: set[str] = set()
        for path in folder.glob("**/workflow.json"):
            workflow_dir = path.parent
            current = workflow_dir.parent
            nested_inside_workflow = False
            while current != folder.parent and current != self.root_dir.parent:
                if (current / "workflow.json").exists():
                    nested_inside_workflow = True
                    break
                current = current.parent
            if not nested_inside_workflow:
                names.add(workflow_dir.relative_to(self.root_dir).as_posix())
        return sorted(names)

    def _is_inside_workflow_dir(self, path: Path) -> bool:
        current = path.resolve(strict=False)
        root = self.root_dir.resolve(strict=False)
        if not current.is_relative_to(root):
            return False
        while current != root:
            if (current / "workflow.json").exists():
                return True
            if current.parent == current:
                return False
            current = current.parent
        return False

    def _rewrite_moved_workflow_metadata(self, old_name: str, new_name: str) -> None:
        if old_name == new_name:
            return
        path = self._path_for(new_name)
        normalize_workflow_draft_identity(path.parent, new_name)
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._write_raw(new_name, raw)

    def _validate_moved_workflows(
        self,
        moves: list[tuple[str, str]],
    ) -> None:
        self._validate_moved_workflow_drafts(moves)

    def _validate_moved_workflow_drafts(
        self,
        moves: list[tuple[str, str]],
    ) -> None:
        for old_name, new_name in moves:
            if old_name != new_name:
                _prepared_workflow_draft_identity(self.workflow_dir(old_name), new_name)

    def _rewrite_moved_workflows(self, moves: list[tuple[str, str]]) -> None:
        for old_name, new_name in moves:
            self._rewrite_moved_workflow_metadata(old_name, new_name)
        self._rewrite_moved_source_provenance(
            {old_name: new_name for old_name, new_name in moves if old_name != new_name}
        )

    def _write_auxiliary_json(self, path: Path, payload: dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            self._fsync_directory(path.parent)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def _rewrite_moved_source_provenance(self, mapping: dict[str, str]) -> None:
        if not mapping:
            return
        saved_updates: list[tuple[str, WorkflowDocument]] = []
        draft_updates: list[tuple[Path, WorkflowDraftResponse]] = []
        for workflow_id in self._workflow_names_under_folder(self.root_dir):
            document = WorkflowDocument.model_validate(self._read_raw(workflow_id))
            graph = rewrite_workspace_source_ids(document.graph, mapping)
            if graph != document.graph:
                saved_updates.append((workflow_id, document.model_copy(update={"graph": graph})))
            draft_path = self._workflow_dir(workflow_id) / ".bioimageflow" / "draft.json"
            if draft_path.exists():
                draft = WorkflowDraftResponse.model_validate_json(
                    draft_path.read_text(encoding="utf-8")
                )
                graph = rewrite_workspace_source_ids(draft.graph, mapping)
                if graph != draft.graph:
                    draft_updates.append((draft_path, draft.model_copy(update={"graph": graph})))

        snapshot_updates: list[tuple[Path, NestedWorkflowSnapshotResponse]] = []
        snapshot_dir = self.workspace_dir / ".bioimageflow" / "nested-workflow-snapshots"
        if snapshot_dir.exists():
            for path in snapshot_dir.glob("*.json"):
                snapshot = NestedWorkflowSnapshotResponse.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                graph = rewrite_workspace_source_ids(snapshot.graph, mapping)
                if graph != snapshot.graph:
                    snapshot_updates.append((path, snapshot.model_copy(update={"graph": graph})))

        for workflow_id, document in saved_updates:
            self._write_raw(
                workflow_id,
                document.model_dump(mode="json", by_alias=True, exclude_none=True),
            )
        for path, draft in draft_updates:
            self._write_auxiliary_json(path, draft.model_dump(mode="json"))
        for path, snapshot in snapshot_updates:
            self._write_auxiliary_json(path, snapshot.model_dump(mode="json"))

    @staticmethod
    def _renamed_child_path(old_name: str, old_prefix: str, new_prefix: str) -> str:
        suffix = old_name[len(old_prefix) :]
        return f"{new_prefix}{suffix}" if new_prefix else suffix.lstrip("/")

    @staticmethod
    def _promoted_child_path(old_name: str, removed_prefix: str, parent_prefix: str) -> str:
        suffix = old_name[len(removed_prefix) :].lstrip("/")
        return f"{parent_prefix}/{suffix}" if parent_prefix else suffix

    def _identity_move_plans(
        self,
        moves: list[tuple[str, str]],
    ) -> list[WorkflowIdentityMovePlan]:
        old_names = [old_name for old_name, new_name in moves if old_name != new_name]
        old_generations = self._capture_workflow_generations(old_names)
        return [
            WorkflowIdentityMovePlan(
                old_workflow_id=old_name,
                old_identity_generation=old_generations[old_name],
                new_workflow_id=new_name,
            )
            for old_name, new_name in moves
            if old_name != new_name
        ]

    def prepare_workflow_patch_move(
        self,
        name: str,
        patch: WorkflowUpdate,
    ) -> UUID | None:
        """Preflight and durably describe a direct identity move before mutation."""

        with self.workflow_structure_mutation():
            self._ensure_no_pending_workflow_move()
            safe_name = self._validate_name(name)
            new_name = self._updated_workflow_name(safe_name, patch)
            if patch.action == "duplicate" or new_name == safe_name:
                return None
            with self.workflow_mutations([safe_name, new_name]):
                self._existing_path_for(safe_name)
                if self._has_name_collision(new_name):
                    raise FileExistsError(new_name)
                moves = [(safe_name, new_name)]
                self._validate_moved_workflows(moves)
                return self._persist_prepared_workflow_move(
                    operation_kind="direct_workflow_move",
                    source_path=safe_name,
                    destination_path=new_name,
                    moves=moves,
                    patches={safe_name: patch},
                )

    def prepare_folder_rename_move(self, path: str, new_path: str) -> UUID | None:
        """Preflight and durably describe an entire folder rename."""

        with self.workflow_structure_mutation():
            self._ensure_no_pending_workflow_move()
            old_folder = self._folder_path(path)
            new_folder = self._folder_path(new_path)
            if (
                not old_folder.exists()
                or not old_folder.is_dir()
                or (old_folder / "workflow.json").exists()
                or self._is_inside_workflow_dir(old_folder)
            ):
                raise FileNotFoundError(path)
            if self._is_inside_workflow_dir(new_folder):
                raise ValueError(
                    "Folders must stay under the workflows root, not inside a workflow"
                )
            if new_folder.exists():
                raise FileExistsError(new_path)
            try:
                new_folder.relative_to(old_folder)
            except ValueError:
                pass
            else:
                raise ValueError("Cannot move a folder into itself")

            safe_old = validate_workflow_id(path)
            safe_new = validate_workflow_id(new_path)
            moves = self._renamed_workflow_moves(old_folder, safe_old, safe_new)
            identities = [identity for move in moves for identity in move]
            with self.workflow_mutations(identities):
                self._validate_moved_workflows(moves)
                return self._persist_prepared_workflow_move(
                    operation_kind="folder_rename",
                    source_path=safe_old,
                    destination_path=safe_new,
                    moves=moves,
                )

    def prepare_folder_promotion_move(self, path: str) -> UUID | None:
        """Preflight and durably describe moving a folder's children to its parent."""

        with self.workflow_structure_mutation():
            self._ensure_no_pending_workflow_move()
            folder = self._folder_path(path)
            if (
                not folder.exists()
                or not folder.is_dir()
                or (folder / "workflow.json").exists()
                or self._is_inside_workflow_dir(folder)
            ):
                raise FileNotFoundError(path)
            children = sorted(folder.iterdir(), key=lambda child: child.name)
            if not children:
                return None
            for child in children:
                destination = folder.parent / child.name
                if destination.exists():
                    raise FileExistsError(destination.name)

            safe_path = validate_workflow_id(path)
            parent_path, _, _ = safe_path.rpartition("/")
            moves = self._promoted_workflow_moves(safe_path, folder)
            identities = [identity for move in moves for identity in move]
            promotion_children = [
                WorkflowPromotionChildMove(
                    source_relative_path=child.relative_to(self.root_dir).as_posix(),
                    destination_relative_path=(folder.parent / child.name)
                    .relative_to(self.root_dir)
                    .as_posix(),
                )
                for child in children
            ]
            with self.workflow_mutations(identities):
                self._validate_moved_workflows(moves)
                return self._persist_prepared_workflow_move(
                    operation_kind="folder_promotion",
                    source_path=safe_path,
                    destination_path=parent_path,
                    moves=moves,
                    promotion_children=promotion_children,
                )

    def _ensure_no_pending_workflow_move(self) -> None:
        pending = self.pending_workflow_move()
        if pending is not None:
            raise WorkflowMoveRecoveryError(
                f"Workflow move {pending.operation_id} must complete before another move"
            )

    def _persist_prepared_workflow_move(
        self,
        *,
        operation_kind: WorkflowMoveKind,
        source_path: str,
        destination_path: str,
        moves: list[tuple[str, str]],
        patches: dict[str, WorkflowUpdate] | None = None,
        promotion_children: list[WorkflowPromotionChildMove] | None = None,
    ) -> UUID:
        generations = self._workflow_move_current_generations(moves)
        artifacts = [
            self._prepare_workflow_artifact_move(
                old_name,
                new_name,
                generations,
                patch=(patches or {}).get(old_name),
            )
            for old_name, new_name in moves
        ]
        operation_id = uuid4()
        journal = WorkflowMoveJournal(
            operation_id=operation_id,
            operation_kind=operation_kind,
            source_path=source_path,
            destination_path=destination_path,
            moves=artifacts,
            promotion_children=promotion_children or [],
        )
        self._write_new_workflow_move_journal(journal)
        return operation_id

    def _workflow_move_current_generations(
        self,
        moves: list[tuple[str, str]],
    ) -> dict[str, int]:
        names = sorted({identity for move in moves for identity in move})
        with self._workflow_generations_guard:
            persisted = self._load_workflow_generation_ledger()
            return {
                name: max(
                    self._workflow_generations.get(name, 0),
                    persisted.get(name, 0),
                )
                for name in names
            }

    def _prepare_workflow_artifact_move(
        self,
        old_name: str,
        new_name: str,
        generations: dict[str, int],
        *,
        patch: WorkflowUpdate | None,
    ) -> WorkflowArtifactMove:
        raw = self._read_raw(old_name)
        document = WorkflowDocument.model_validate(raw)
        raw_metadata = raw.get("metadata", {})
        metadata = (
            cast(dict[str, Any], json.loads(json.dumps(raw_metadata)))
            if isinstance(raw_metadata, dict)
            else {}
        )
        metadata = {key: value for key, value in metadata.items() if value is not None}
        if patch is not None and patch.description is not None:
            metadata["description"] = patch.description

        source_generation = generations[old_name]
        destination_generation = generations[new_name]
        return WorkflowArtifactMove(
            source_workflow_id=old_name,
            destination_workflow_id=new_name,
            source_generation_before=source_generation,
            source_generation_after=source_generation + 1,
            destination_generation_before=destination_generation,
            destination_generation_after=destination_generation + 1,
            target_metadata=metadata,
            target_display_name=(
                patch.display_name
                if patch is not None and patch.display_name is not None
                else document.graph.display_name
            ),
        )

    def _metadata_from_raw(
        self,
        name: str,
        raw: dict[str, Any],
        path: Path,
    ) -> WorkflowInfo:
        document = WorkflowDocument.model_validate(raw)
        metadata = document.metadata
        last_modified = datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=UTC,
        ).isoformat()
        return WorkflowInfo(
            id=name,
            name=self._leaf_name(name),
            folder=self._folder_name(name),
            display_name=document.graph.display_name,
            description=metadata.description,
            workspace_path=str(self.workspace_dir),
            results_path=str(self.get_storage_path(name)),
            path=str(path),
            last_modified=last_modified,
            identity_generation=self.workflow_generation(name),
        )

    def _read_raw(self, name: str) -> dict[str, Any]:
        path = self._existing_path_for(name)
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Workflow file {path} must contain a JSON object")
        return WorkflowDocument.model_validate(data).model_dump(mode="json", by_alias=True)

    def get_storage_path(self, name: str) -> Path:
        """Return the workflow-local runtime results directory."""
        self._existing_path_for(name)
        return self._workflow_dir(name) / "results"

    def _write_raw(self, name: str, raw: dict[str, Any]) -> None:
        raw = WorkflowDocument.model_validate(raw).model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        path = self._path_for(name)
        self._ensure_workflow_layout(name)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{self._leaf_name(name)}.",
            suffix=".tmp.json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(raw, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
            self._fsync_directory(path.parent)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def _empty_raw(self, data: WorkflowCreate) -> dict[str, Any]:
        definition_name = self._leaf_name(data.name)
        graph = GraphState(
            schema_version=2,
            name=definition_name,
            display_name=data.display_name or definition_name,
            nodes=[],
            edges=[],
            interface={"inputs": [], "outputs": []},
            config={},
        )
        return WorkflowDocument(
            graph=graph,
            metadata=WorkspaceWorkflowMetadata(
                description=data.description,
            ),
            artifact_hash=artifact_hash(graph, []),
        ).model_dump(mode="json", by_alias=True, exclude_none=True)

    def validate_containment(self, destination: str, graph: GraphState) -> None:
        validate_workflow_containment(
            destination,
            graph,
            resolve_saved_graph=lambda workflow_id: self.get_workflow(workflow_id).graph,
        )

    def suggest_name(self, base_name: str) -> str:
        base = self._validate_name(base_name)
        candidate = base
        suffix = 2
        while self._has_name_collision(candidate):
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @_identity_locked
    def export_workflow_archive(self, name: str) -> tuple[str, bytes]:
        self._existing_path_for(name)
        document = WorkflowDocument.model_validate(self._read_raw(name))
        export_graph, sources = capture_working_graph(
            document.graph, self._workflow_dir(name), self.tool_registry
        )
        translation = graph_state_to_lib_dict(
            export_graph,
            self.tool_registry,
        )
        if translation.errors:
            raise WorkflowArchiveError("; ".join(error.detail for error in translation.errors))
        payload = capture_library_sources(translation.lib_dict, sources)
        filename = f"{safe_workflow_export_stem(self._validate_name(name))}.bioimageflow.zip"
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = Path(tmp_dir) / filename
            try:
                self.archive_adapter.export_archive(
                    payload,
                    archive_path,
                    storage_path=self.get_storage_path(name),
                )
                return filename, archive_path.read_bytes()
            except Exception as exc:
                raise WorkflowArchiveError(str(exc)) from exc

    def _archive_name_from_filename(self, filename: str | None) -> str:
        if filename:
            name = Path(filename).name
            for suffix in (".bioimageflow.zip", ".zip"):
                if name.endswith(suffix):
                    return self._validate_name(name[: -len(suffix)])
            return self._validate_name(Path(name).stem)
        return self.suggest_name("workflow")

    def import_workflow_archive(
        self,
        raw_archive: bytes,
        *,
        filename: str | None = None,
        name_override: str | None = None,
    ) -> WorkflowImportResponse:
        try:
            with zipfile.ZipFile(BytesIO(raw_archive)) as archive:
                is_results_bundle = "bioimageflow-results-bundle.json" in archive.namelist()
        except zipfile.BadZipFile:
            is_results_bundle = False
        if is_results_bundle:
            raise WorkflowResultsBundleImportError(
                "Workflow-and-results bundles are export artifacts and cannot be imported "
                "as portable workflow archives. Export the workflow-only archive instead."
            )
        imported_name = self._validate_name(
            name_override or self._archive_name_from_filename(filename)
        )
        with self.workflow_structure_mutation(), self.workflow_mutation(imported_name):
            self.ensure_workflow_mutations_available()
            if self._has_name_collision(imported_name):
                raise FileExistsError(imported_name)
            self._reserve_workflow_generations([imported_name])
            return self._import_workflow_archive_locked(
                raw_archive,
                filename=filename,
                imported_name=imported_name,
                rename_graph=bool(name_override),
            )

    def _import_workflow_archive_locked(
        self,
        raw_archive: bytes,
        *,
        filename: str | None,
        imported_name: str,
        rename_graph: bool,
    ) -> WorkflowImportResponse:
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = Path(tmp_dir) / "workflow.bioimageflow.zip"
            archive_path.write_bytes(raw_archive)
            try:
                inspect = getattr(self.archive_adapter, "inspect_viewing_requirements", None)
                viewing_requirements = ViewingRequirementsManifest.model_validate(
                    inspect(archive_path) if callable(inspect) else {}
                )
                library = self.archive_adapter.read_archive(
                    archive_path,
                    storage_path=Path(tmp_dir) / "results",
                )
            except Exception as exc:
                raise WorkflowArchiveError(str(exc)) from exc
            if not isinstance(library, dict):
                raise WorkflowArchiveError("Workflow archive did not contain a workflow object")
            try:
                graph = lib_dict_to_graph_state(library)
            except (TypeError, ValueError, ValidationError) as exc:
                raise WorkflowArchiveError(str(exc)) from exc
            if rename_graph:
                graph = graph.model_copy(
                    update={
                        "name": self._leaf_name(imported_name),
                        "display_name": self._leaf_name(imported_name),
                    }
                )
            self.validate_containment(imported_name, graph)
            source_records = (
                library.get("custom_sources", [])
                if library.get("archive_version") in {1, 2}
                else []
            )
            if not isinstance(source_records, list):
                raise WorkflowArchiveError("Workflow archive sources must be an array")
            destination = self._workflow_dir(imported_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".workflow-import-", dir=destination.parent))
            sources = OwnedWorkflowSources(staging)
            document = WorkflowDocument(
                graph=graph,
                metadata=WorkspaceWorkflowMetadata(
                    description=None,
                ),
                owned_source_ids=sorted(referenced_source_ids(graph)),
                artifact_hash=artifact_hash(graph, cast(list[dict[str, Any]], source_records)),
            )
            try:
                staged = sources.stage(cast(list[dict[str, Any]], source_records))
                sources.publish(staged)
                sources.collect_for_graph(graph)
                with (staging / "workflow.json").open("w", encoding="utf-8") as handle:
                    json.dump(
                        document.model_dump(mode="json", by_alias=True, exclude_none=True),
                        handle,
                        indent=2,
                    )
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(staging, destination)
                self._fsync_directory(destination.parent)
                loaded = self.get_workflow(imported_name)
                return WorkflowImportResponse(
                    info=loaded.info,
                    missing_packages=loaded.missing_packages,
                    missing_tools=loaded.missing_tools,
                    viewing_requirements=viewing_requirements,
                )
            finally:
                shutil.rmtree(staging, ignore_errors=True)

    def list_workflows(self) -> list[WorkflowInfo]:
        if not self.root_dir.exists():
            return []
        workflows: list[WorkflowInfo] = []
        _plan_id, _targets, pending_ids, _scan_errors = self._plan_schema_v2_workflows()
        names = {
            path.parent.relative_to(self.root_dir).as_posix()
            for path in self.root_dir.glob("**/workflow.json")
            if not path.name.startswith(".")
            and not self._is_inside_workflow_dir(path.parent.parent)
        }
        for name in sorted(names):
            if name.startswith(".") or name in pending_ids:
                continue
            try:
                with self.workflow_mutation(name):
                    path = self._existing_path_for(name)
                    raw = self._read_raw(name)
                    workflows.append(self._metadata_from_raw(name, raw, path))
            except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
                logger.warning("Workflow %s is hidden because its format is invalid: %s", name, exc)
                continue
        return workflows

    def migrate_legacy_workflows(self) -> list[WorkflowFormatNotice]:
        """Upgrade recognized pre-recursive documents without hiding failures."""

        if not self.root_dir.exists():
            return []
        notices: list[WorkflowFormatNotice] = []
        paths = sorted(self.root_dir.glob("**/workflow.json"))
        for path in paths:
            if self._is_inside_workflow_dir(path.parent.parent):
                continue
            workflow_id = path.parent.relative_to(self.root_dir).as_posix()
            try:
                with self.workflow_mutation(workflow_id):
                    notice = migrate_legacy_workflow(path, workflow_id)
                if notice is not None:
                    notices.append(notice)
                    logger.warning("%s Backups: %s", notice.detail, ", ".join(notice.backup_paths))
            except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
                logger.warning("Could not migrate workflow %s: %s", workflow_id, exc)
        self._workflow_format_notices.extend(notices)
        return notices

    def _plan_schema_v2_workflows(
        self,
    ) -> tuple[
        str | None,
        list[dict[str, Any]],
        set[str],
        list[WorkflowFormatNotice],
    ]:
        """Build a content-derived migration preview without writing anything."""

        def requires_schema_v2(raw_graph: Any) -> bool:
            if not isinstance(raw_graph, dict):
                return False
            if raw_graph.get("schema_version") == 1:
                return True
            nodes = raw_graph.get("nodes")
            return isinstance(nodes, list) and any(
                isinstance(node, dict)
                and node.get("type") == "workflow"
                and requires_schema_v2(node.get("workflow"))
                for node in nodes
            )

        if not self.root_dir.exists():
            return None, [], set(), []

        paths = [
            path
            for path in sorted(self.root_dir.glob("**/workflow.json"))
            if not self._is_inside_workflow_dir(path.parent.parent)
        ]
        raw_documents: dict[str, dict[str, Any]] = {}
        documents: dict[str, WorkflowDocument] = {}
        tool_metadata: dict[str, dict[str, dict[str, Any]]] = {}
        saved_requires_update: set[str] = set()
        for path in paths:
            workflow_id = path.parent.relative_to(self.root_dir).as_posix()
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict) or "graph" not in raw:
                continue
            try:
                document = WorkflowDocument.model_validate(raw)
            except ValidationError:
                try:
                    document, legacy_tool_metadata = normalize_legacy_workflow_document(
                        raw, workflow_id
                    )
                except (ValidationError, ValueError):
                    continue
                tool_metadata[workflow_id] = legacy_tool_metadata
                saved_requires_update.add(workflow_id)
            else:
                _document, current_tool_metadata = normalize_legacy_workflow_document(
                    raw, workflow_id
                )
                tool_metadata[workflow_id] = current_tool_metadata
            raw_documents[workflow_id] = raw
            documents[workflow_id] = document
            if requires_schema_v2(raw.get("graph")):
                saved_requires_update.add(workflow_id)

        old_to_new_hash: dict[str, str] = {}
        new_hashes: dict[str, str] = {}
        for workflow_id, document in documents.items():
            if workflow_id in saved_requires_update:
                sources = OwnedWorkflowSources(self._workflow_dir(workflow_id)).collect_for_graph(
                    document.graph
                )
                new_hash = artifact_hash(document.graph, sources)
            else:
                new_hash = document.artifact_hash
            new_hashes[workflow_id] = new_hash
            old_hash = raw_documents[workflow_id].get("artifact_hash")
            if isinstance(old_hash, str):
                old_to_new_hash[old_hash] = new_hash

        targets: list[dict[str, Any]] = []
        migrated_ids: set[str] = set()
        scan_errors: list[WorkflowFormatNotice] = []
        for workflow_id, document in documents.items():
            workflow_path = self._path_for(workflow_id)
            graph = rewrite_workspace_source_hashes(document.graph, old_to_new_hash)
            migrated_document = document.model_copy(
                update={
                    "graph": graph,
                    "artifact_hash": new_hashes[workflow_id],
                }
            ).model_dump(mode="json", by_alias=True, exclude_none=True)
            if workflow_id in saved_requires_update or graph != document.graph:
                migrated_ids.add(workflow_id)
                targets.append(self._schema_v2_target(workflow_path, migrated_document))

            draft_path = workflow_path.parent / ".bioimageflow" / "draft.json"
            if not draft_path.is_file():
                continue
            try:
                raw_draft = json.loads(draft_path.read_text(encoding="utf-8"))
                try:
                    draft = WorkflowDraftResponse.model_validate(raw_draft)
                    legacy_draft = False
                except ValidationError:
                    draft = normalize_legacy_workflow_draft(
                        raw_draft,
                        workflow_id=workflow_id,
                        document=document,
                        tool_metadata=tool_metadata[workflow_id],
                    )
                    legacy_draft = True
            except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
                scan_errors.append(
                    WorkflowFormatNotice(
                        status="error",
                        workflow_id=workflow_id,
                        path=str(draft_path),
                        detail=f"The editing draft could not be prepared for update: {exc}",
                    )
                )
                continue
            draft_graph = rewrite_workspace_source_hashes(draft.graph, old_to_new_hash)
            draft_requires_update = (
                legacy_draft
                or requires_schema_v2(raw_draft.get("graph"))
                or draft_graph != draft.graph
                or workflow_id in saved_requires_update
            )
            if not draft_requires_update:
                continue
            sources = OwnedWorkflowSources(workflow_path.parent).collect_for_graph(draft_graph)
            dirty = artifact_hash(draft_graph, sources) != new_hashes[workflow_id]
            base_saved_revision = old_to_new_hash.get(
                draft.base_saved_revision,
                new_hashes[workflow_id]
                if not draft.dirty_against_saved
                else draft.base_saved_revision,
            )
            migrated_draft = draft.model_copy(
                update={
                    "graph": draft_graph,
                    "base_saved_revision": base_saved_revision,
                    "dirty_against_saved": dirty,
                }
            ).model_dump(mode="json", by_alias=True, exclude_none=True)
            if draft_requires_update:
                migrated_ids.add(workflow_id)
                targets.append(self._schema_v2_target(draft_path, migrated_draft))

        snapshot_dir = self.workspace_dir / ".bioimageflow" / "nested-workflow-snapshots"
        if snapshot_dir.is_dir():
            snapshots: dict[UUID, NestedWorkflowSnapshotResponse] = {}
            raw_snapshots: dict[UUID, tuple[Path, dict[str, Any]]] = {}
            for snapshot_path in sorted(snapshot_dir.glob("*.json")):
                try:
                    raw_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                    if not isinstance(raw_snapshot, dict) or "graph" not in raw_snapshot:
                        raise ValueError("snapshot does not contain a graph")
                    snapshot = NestedWorkflowSnapshotResponse.model_validate(raw_snapshot)
                except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
                    scan_errors.append(
                        WorkflowFormatNotice(
                            status="error",
                            workflow_id="nested snapshot",
                            path=str(snapshot_path),
                            detail=f"A nested editing snapshot could not be prepared for update: {exc}",
                        )
                    )
                    continue
                snapshots[snapshot.session_id] = snapshot
                raw_snapshots[snapshot.session_id] = (snapshot_path, raw_snapshot)

            def root_workflow_id(
                snapshot: NestedWorkflowSnapshotResponse,
            ) -> str | None:
                seen: set[UUID] = set()
                current = snapshot
                while current.owner.kind == "nested":
                    parent_id = current.owner.session_id
                    if parent_id is None or parent_id in seen:
                        return None
                    seen.add(parent_id)
                    parent = snapshots.get(parent_id)
                    if parent is None:
                        return None
                    current = parent
                return current.owner.workflow_id

            for session_id, snapshot in snapshots.items():
                snapshot_path, raw_snapshot = raw_snapshots[session_id]
                migrated_snapshot = snapshot.model_copy(
                    update={
                        "graph": rewrite_workspace_source_hashes(snapshot.graph, old_to_new_hash)
                    }
                ).model_dump(mode="json", by_alias=True, exclude_none=True)
                if requires_schema_v2(raw_snapshot.get("graph")) or migrated_snapshot[
                    "graph"
                ] != snapshot.graph.model_dump(mode="json", by_alias=True, exclude_none=True):
                    targets.append(self._schema_v2_target(snapshot_path, migrated_snapshot))
                    owner_workflow_id = root_workflow_id(snapshot)
                    if owner_workflow_id is not None:
                        migrated_ids.add(owner_workflow_id)

        if not targets:
            return None, [], set(), scan_errors
        plan_material = [
            {
                "kind": target["kind"],
                "path": target["path"],
                "source_digest": target["source_digest"],
                "target_digest": target["target_digest"],
            }
            for target in targets
        ]
        plan_id = f"sha256:{hashlib.sha256(canonical_json_bytes(plan_material)).hexdigest()}"
        backup_root = (
            Path(".bioimageflow")
            / "backups"
            / "workflow-format"
            / _workflow_format_plan_directory(plan_id)
        )
        for target in targets:
            target["backup_path"] = (backup_root / target["path"]).as_posix()
        return plan_id, targets, migrated_ids, scan_errors

    def migrate_schema_v2_workflows(self) -> list[WorkflowFormatNotice]:
        """Compatibility helper that explicitly confirms the current preview."""

        status = self.workflow_format_status()
        if status.pending_plan_id is None:
            return []
        applied = self.apply_workflow_format_migrations(status.pending_plan_id)
        return [notice for notice in applied.notices if notice.status == "migrated"]

    def apply_workflow_format_migrations(
        self,
        pending_plan_id: str,
    ) -> WorkflowFormatStatus:
        """Apply exactly one previewed plan as a forward-recoverable transaction."""

        with self.workflow_structure_mutation():
            self._recover_schema_v2_migration()
            plan_id, targets, migrated_ids, _scan_errors = self._plan_schema_v2_workflows()
            if plan_id != pending_plan_id or plan_id is None:
                raise WorkflowFormatPlanStaleError(
                    "Workflow files changed after the format update preview; review again."
                )
            self._create_schema_v2_backups(plan_id, targets)
            journal = {
                "version": 2,
                "confirmed": True,
                "plan_id": plan_id,
                "targets": targets,
            }
            self._write_schema_v2_json(self._schema_v2_migration_journal_path, journal)
            self._apply_schema_v2_targets(targets, plan_id=plan_id)
            self._schema_v2_migration_journal_path.unlink()
            self._fsync_directory(self._schema_v2_migration_journal_path.parent)
            all_backups = [str(self.workspace_dir / target["backup_path"]) for target in targets]
            notices = [
                WorkflowFormatNotice(
                    status="migrated",
                    workflow_id=workflow_id,
                    path=str(self._path_for(workflow_id)),
                    detail="Updated the saved workflow and editing state to schema v2.",
                    backup_paths=[
                        backup
                        for target, backup in zip(targets, all_backups, strict=True)
                        if target["path"].startswith(
                            self._workflow_dir(workflow_id)
                            .relative_to(self.workspace_dir)
                            .as_posix()
                            + "/"
                        )
                    ],
                )
                for workflow_id in sorted(migrated_ids)
            ]
            assigned = {path for notice in notices for path in notice.backup_paths}
            if notices:
                notices[0].backup_paths.extend(path for path in all_backups if path not in assigned)
            self._workflow_format_notices = notices
            return self.workflow_format_status()

    def _schema_v2_target(self, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        kind = self._schema_v2_target_kind(path)
        return {
            "kind": kind,
            "path": path.relative_to(self.workspace_dir).as_posix(),
            "source_digest": f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}",
            "target_payload": payload,
            "target_digest": f"sha256:{hashlib.sha256(_schema_v2_json_bytes(payload)).hexdigest()}",
        }

    def _schema_v2_target_kind(self, path: Path) -> str:
        resolved = path.resolve(strict=False)
        root = self.root_dir.resolve(strict=False)
        snapshots = (self.workspace_dir / ".bioimageflow" / "nested-workflow-snapshots").resolve(
            strict=False
        )
        if resolved.name == "workflow.json" and resolved.is_relative_to(root):
            workflow_dir = resolved.parent
            if workflow_dir != root and not self._is_inside_workflow_dir(workflow_dir.parent):
                return "saved_workflow"
        if (
            resolved.name == "draft.json"
            and resolved.parent.name == ".bioimageflow"
            and (resolved.parent.parent / "workflow.json").is_file()
            and resolved.parent.parent.resolve(strict=False).is_relative_to(root)
        ):
            return "root_draft"
        if resolved.parent == snapshots and resolved.suffix == ".json":
            try:
                UUID(resolved.stem)
            except ValueError:
                pass
            else:
                return "nested_snapshot"
        raise WorkflowMoveRecoveryError(
            f"Schema-v2 migration target is not an authorized workflow artifact: {path}"
        )

    def _recover_schema_v2_migration(self) -> None:
        path = self._schema_v2_migration_journal_path
        if not path.is_file():
            return
        raw = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(raw, dict)
            or set(raw) != {"version", "confirmed", "plan_id", "targets"}
            or raw.get("version") != 2
            or raw.get("confirmed") is not True
            or not isinstance(raw.get("plan_id"), str)
            or not isinstance(raw.get("targets"), list)
        ):
            raise WorkflowMoveRecoveryError(f"Cannot trust schema-v2 migration journal: {path}")
        _workflow_format_plan_directory(raw["plan_id"])
        self._apply_schema_v2_targets(raw["targets"], plan_id=raw["plan_id"])
        path.unlink()
        self._fsync_directory(path.parent)

    def recover_workflow_format_migration(self) -> None:
        """Finish an already-confirmed format transaction after a crash."""

        with self.workflow_structure_mutation():
            self._recover_schema_v2_migration()

    def _create_schema_v2_backups(
        self,
        plan_id: str,
        targets: list[dict[str, Any]],
    ) -> None:
        for target in targets:
            source = self.workspace_dir / str(target["path"])
            content = source.read_bytes()
            source_digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
            if source_digest != target["source_digest"]:
                raise WorkflowFormatPlanStaleError(
                    "Workflow files changed after the format update preview; review again."
                )
            backup = self.workspace_dir / str(target["backup_path"])
            expected_root = (
                self.workspace_dir
                / ".bioimageflow"
                / "backups"
                / "workflow-format"
                / _workflow_format_plan_directory(plan_id)
            )
            if not backup.resolve(strict=False).is_relative_to(expected_root.resolve(strict=False)):
                raise WorkflowMoveRecoveryError(
                    "Schema-v2 migration backup escapes its plan directory"
                )
            self._ensure_directory_durable(backup.parent)
            if backup.exists():
                if backup.read_bytes() != content:
                    raise WorkflowMoveRecoveryError(
                        f"Schema-v2 migration backup collision: {backup}"
                    )
                continue
            descriptor, temporary = tempfile.mkstemp(
                dir=str(backup.parent), prefix=f".{backup.name}.", suffix=".tmp"
            )
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, backup)
                self._fsync_directory(backup.parent)
            except Exception:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise

    def _apply_schema_v2_targets(
        self,
        targets: list[Any],
        *,
        plan_id: str,
    ) -> None:
        for target in targets:
            if not isinstance(target, dict) or set(target) != {
                "kind",
                "path",
                "source_digest",
                "backup_path",
                "target_payload",
                "target_digest",
            }:
                raise WorkflowMoveRecoveryError("Cannot trust schema-v2 migration target")
            relative = Path(str(target["path"]))
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise WorkflowMoveRecoveryError("Schema-v2 migration target escapes workspace")
            destination = self.workspace_dir / relative
            if not destination.resolve(strict=False).is_relative_to(
                self.workspace_dir.resolve(strict=False)
            ):
                raise WorkflowMoveRecoveryError("Schema-v2 migration target escapes workspace")
            kind = self._schema_v2_target_kind(destination)
            if target["kind"] != kind:
                raise WorkflowMoveRecoveryError(
                    "Schema-v2 migration target kind does not match its authority"
                )
            backup = self.workspace_dir / str(target["backup_path"])
            expected_backup_root = (
                self.workspace_dir
                / ".bioimageflow"
                / "backups"
                / "workflow-format"
                / _workflow_format_plan_directory(plan_id)
            )
            if (
                not backup.resolve(strict=False).is_relative_to(
                    expected_backup_root.resolve(strict=False)
                )
                or not backup.is_file()
            ):
                raise WorkflowMoveRecoveryError("Schema-v2 migration backup is missing or unsafe")
            source_digest = f"sha256:{hashlib.sha256(backup.read_bytes()).hexdigest()}"
            if source_digest != target["source_digest"]:
                raise WorkflowMoveRecoveryError(
                    "Schema-v2 migration backup digest does not match its source"
                )
            payload = target["target_payload"]
            if not isinstance(payload, dict):
                raise WorkflowMoveRecoveryError("Schema-v2 migration payload is invalid")
            expected_digest = f"sha256:{hashlib.sha256(_schema_v2_json_bytes(payload)).hexdigest()}"
            if target["target_digest"] != expected_digest:
                raise WorkflowMoveRecoveryError(
                    "Schema-v2 migration target digest does not match its payload"
                )
            try:
                if kind == "saved_workflow":
                    validated = WorkflowDocument.model_validate(payload)
                elif kind == "root_draft":
                    validated = WorkflowDraftResponse.model_validate(payload)
                    workflow_id = destination.parent.parent.relative_to(self.root_dir).as_posix()
                    if validated.workflow_id != workflow_id:
                        raise ValueError("Draft workflow identity does not match its path")
                else:
                    validated = NestedWorkflowSnapshotResponse.model_validate(payload)
                    if validated.session_id != UUID(destination.stem):
                        raise ValueError("Snapshot session identity does not match its path")
                if validated.graph.schema_version != 2:
                    raise ValueError("Migration target graph is not canonical schema v2")
                normalized = validated.model_dump(mode="json", by_alias=True, exclude_none=True)
            except (ValidationError, ValueError) as exc:
                raise WorkflowMoveRecoveryError(
                    f"Schema-v2 migration {kind} payload is invalid"
                ) from exc
            if normalized != payload:
                raise WorkflowMoveRecoveryError(
                    f"Schema-v2 migration {kind} payload is not canonical"
                )
            current_digest = (
                f"sha256:{hashlib.sha256(destination.read_bytes()).hexdigest()}"
                if destination.is_file()
                else None
            )
            if current_digest == target["target_digest"]:
                continue
            if current_digest != target["source_digest"]:
                raise WorkflowMoveRecoveryError(
                    "Schema-v2 migration source changed after confirmation"
                )
            self._write_schema_v2_json(destination, payload)

    def _write_schema_v2_json(self, path: Path, payload: dict[str, Any]) -> None:
        self._ensure_directory_durable(path.parent)
        fd, temporary = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            self._fsync_directory(path.parent)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def workflow_format_status(self) -> WorkflowFormatStatus:
        """Preview pending migrations and report invalid workflow files."""

        notices = list(self._workflow_format_notices)
        plan_id, _targets, pending_ids, scan_errors = self._plan_schema_v2_workflows()
        notices.extend(scan_errors)
        notices.extend(
            WorkflowFormatNotice(
                status="pending",
                workflow_id=workflow_id,
                path=str(self._path_for(workflow_id)),
                detail="This workflow must be updated to schema v2 before it can be opened.",
            )
            for workflow_id in sorted(pending_ids)
        )
        if self.root_dir.exists():
            for path in sorted(self.root_dir.glob("**/workflow.json")):
                if self._is_inside_workflow_dir(path.parent.parent):
                    continue
                workflow_id = path.parent.relative_to(self.root_dir).as_posix()
                issue = workflow_format_error(path, workflow_id)
                if issue is not None and workflow_id not in pending_ids:
                    notices.append(issue)
        return WorkflowFormatStatus(notices=notices, pending_plan_id=plan_id)

    def ensure_workflow_format_current(self, name: str) -> None:
        """Reject editable access to one workflow covered by a pending plan."""

        safe_name = self._validate_name(name)
        _plan_id, _targets, pending_ids, _scan_errors = self._plan_schema_v2_workflows()
        if safe_name in pending_ids:
            raise WorkflowFormatUpdateRequiredError(safe_name)

    def workflow_tree(self) -> WorkflowFolderInfo:
        """Return workflows grouped by workspace-relative folders."""
        root = WorkflowFolderInfo(path="", display_name="workspace")
        folders: dict[str, WorkflowFolderInfo] = {"": root}

        def ensure_folder(path: str) -> WorkflowFolderInfo:
            if path in folders:
                return folders[path]
            parent_path, _, leaf = path.rpartition("/")
            parent = ensure_folder(parent_path)
            folder = WorkflowFolderInfo(path=path, display_name=leaf or path)
            parent.folders.append(folder)
            parent.folders.sort(key=lambda item: item.display_name.lower())
            folders[path] = folder
            return folder

        for workflow in self.list_workflows():
            folder = ensure_folder(workflow.folder)
            folder.workflows.append(workflow)
            folder.workflows.sort(key=lambda item: item.display_name.lower())

        if self.root_dir.exists():
            for path in self.root_dir.glob("**"):
                if not path.is_dir() or path == self.root_dir:
                    continue
                if self._is_inside_workflow_dir(path):
                    continue
                rel = path.relative_to(self.root_dir).as_posix()
                ensure_folder(rel)
        return root

    def _folder_path(self, path: str) -> Path:
        safe = validate_workflow_id(path)
        return self.root_dir.joinpath(*safe.split("/"))

    def create_folder(self, path: str) -> WorkflowFolderInfo:
        with self.workflow_structure_mutation():
            self.ensure_workflow_mutations_available()
            folder = self._folder_path(path)
            if self._is_inside_workflow_dir(folder):
                raise ValueError(
                    "Folders must be created under the workflows root, not inside a workflow"
                )
            if folder.exists():
                raise FileExistsError(path)
            folder.mkdir(parents=True)
            safe = validate_workflow_id(path)
            return WorkflowFolderInfo(path=safe, display_name=safe.split("/")[-1])

    def workflow_names_in_folder(self, path: str) -> list[str]:
        """Return path-derived identities beneath a folder as one tree snapshot."""

        with self.workflow_structure_mutation():
            folder = self._folder_path(path)
            if not folder.exists() or not folder.is_dir():
                raise FileNotFoundError(path)
            return self._workflow_names_under_folder(folder)

    def plan_folder_delete_moves(
        self,
        path: str,
        policy: WorkflowFolderDelete | str,
    ) -> list[WorkflowIdentityMovePlan]:
        """Capture root identity moves caused by promoting a folder's children."""

        with self.workflow_structure_mutation():
            policy_name = policy.policy if isinstance(policy, WorkflowFolderDelete) else policy
            if policy_name != "move_children_up":
                return []
            folder = self._folder_path(path)
            if (
                not folder.exists()
                or not folder.is_dir()
                or (folder / "workflow.json").exists()
                or self._is_inside_workflow_dir(folder)
            ):
                raise FileNotFoundError(path)
            return self._identity_move_plans(self._promoted_workflow_moves(path, folder))

    def _promoted_workflow_moves(
        self,
        path: str,
        folder: Path,
    ) -> list[tuple[str, str]]:
        safe_path = validate_workflow_id(path)
        parent_prefix, _, _ = safe_path.rpartition("/")
        return [
            (name, self._promoted_child_path(name, safe_path, parent_prefix))
            for name in self._workflow_names_under_folder(folder)
        ]

    def delete_folder(
        self,
        path: str,
        policy: WorkflowFolderDelete | str = "empty",
        *,
        move_operation_id: UUID | None = None,
    ) -> None:
        with self.workflow_structure_mutation():
            policy_name = policy.policy if isinstance(policy, WorkflowFolderDelete) else policy
            if policy_name == "move_children_up":
                safe_path = validate_workflow_id(path)
                parent_path, _, _ = safe_path.rpartition("/")
                if move_operation_id is None:
                    self.ensure_workflow_mutations_available()
                    folder = self._folder_path(safe_path)
                    is_plain_folder = (
                        folder.exists()
                        and folder.is_dir()
                        and not (folder / "workflow.json").exists()
                        and not self._is_inside_workflow_dir(folder)
                    )
                    if is_plain_folder and any(folder.iterdir()):
                        raise WorkflowMoveRecoveryError(
                            "Non-empty folder promotion requires a prepared move journal"
                        )
                else:
                    journal = self._require_prepared_workflow_move(
                        move_operation_id,
                        operation_kind="folder_promotion",
                        source_path=safe_path,
                        destination_path=parent_path,
                    )
                    folder = self._folder_path(safe_path)
                    self._validate_prepared_move_execution(
                        journal,
                        self._promoted_workflow_moves(safe_path, folder),
                    )
            else:
                self.ensure_workflow_mutations_available()
                if move_operation_id is not None:
                    raise WorkflowMoveRecoveryError(
                        "Only folder promotion accepts a workflow move operation"
                    )
            self._delete_folder_locked(path, policy)
            if move_operation_id is not None:
                self.mark_workflow_move_phase(
                    move_operation_id,
                    "artifacts_rewritten",
                )

    def _delete_folder_locked(
        self,
        path: str,
        policy: WorkflowFolderDelete | str,
    ) -> None:
        if isinstance(policy, WorkflowFolderDelete):
            policy_name = policy.policy
        else:
            policy_name = policy
        folder = self._folder_path(path)
        if (
            not folder.exists()
            or not folder.is_dir()
            or (folder / "workflow.json").exists()
            or self._is_inside_workflow_dir(folder)
        ):
            raise FileNotFoundError(path)
        children = list(folder.iterdir())
        if children and policy_name == "empty":
            raise FileExistsError(path)
        if children and policy_name == "delete_children":
            workflow_names = self._workflow_names_under_folder(folder)
            with self.workflow_mutations(workflow_names):
                self._reserve_workflow_generations(workflow_names)
                shutil.rmtree(folder)
            return
        if children and policy_name == "move_children_up":
            moves = self._promoted_workflow_moves(path, folder)
            identities = [identity for move in moves for identity in move]
            with self.workflow_mutations(identities):
                children = list(folder.iterdir())
                self._validate_moved_workflows(moves)
                for child in children:
                    destination = folder.parent / child.name
                    if destination.exists():
                        raise FileExistsError(destination.name)
                self._reserve_workflow_generations(identities)
                for child in children:
                    destination = folder.parent / child.name
                    child.rename(destination)
                    self._fsync_directory(folder)
                    self._fsync_directory(destination.parent)
                self._rewrite_moved_workflows(moves)
        folder.rmdir()
        self._fsync_directory(folder.parent)

    def rename_folder(
        self,
        path: str,
        new_path: str,
        *,
        move_operation_id: UUID | None = None,
    ) -> WorkflowFolderInfo:
        with self.workflow_structure_mutation():
            safe_path = validate_workflow_id(path)
            safe_new_path = validate_workflow_id(new_path)
            journal = self._require_prepared_workflow_move(
                move_operation_id,
                operation_kind="folder_rename",
                source_path=safe_path,
                destination_path=safe_new_path,
            )
            old_folder = self._folder_path(safe_path)
            self._validate_prepared_move_execution(
                journal,
                self._renamed_workflow_moves(
                    old_folder,
                    safe_path,
                    safe_new_path,
                ),
            )
            folder = self._rename_folder_locked(path, new_path)
            assert move_operation_id is not None
            self.mark_workflow_move_phase(
                move_operation_id,
                "artifacts_rewritten",
            )
            return folder

    def plan_folder_rename_moves(
        self,
        path: str,
        new_path: str,
    ) -> list[WorkflowIdentityMovePlan]:
        """Capture root identity moves caused by a folder rename."""

        with self.workflow_structure_mutation():
            old_folder = self._folder_path(path)
            if (
                not old_folder.exists()
                or not old_folder.is_dir()
                or (old_folder / "workflow.json").exists()
                or self._is_inside_workflow_dir(old_folder)
            ):
                raise FileNotFoundError(path)
            safe_old = validate_workflow_id(path)
            safe_new = validate_workflow_id(new_path)
            return self._identity_move_plans(
                self._renamed_workflow_moves(old_folder, safe_old, safe_new)
            )

    def _renamed_workflow_moves(
        self,
        old_folder: Path,
        safe_old: str,
        safe_new: str,
    ) -> list[tuple[str, str]]:
        return [
            (name, self._renamed_child_path(name, safe_old, safe_new))
            for name in self._workflow_names_under_folder(old_folder)
        ]

    def _rename_folder_locked(
        self,
        path: str,
        new_path: str,
    ) -> WorkflowFolderInfo:
        old_folder = self._folder_path(path)
        new_folder = self._folder_path(new_path)
        if (
            not old_folder.exists()
            or not old_folder.is_dir()
            or self._is_inside_workflow_dir(old_folder)
        ):
            raise FileNotFoundError(path)
        if (old_folder / "workflow.json").exists():
            raise FileNotFoundError(path)
        if self._is_inside_workflow_dir(new_folder):
            raise ValueError("Folders must stay under the workflows root, not inside a workflow")
        if new_folder.exists():
            raise FileExistsError(new_path)
        try:
            new_folder.relative_to(old_folder)
        except ValueError:
            pass
        else:
            raise ValueError("Cannot move a folder into itself")
        safe_old = validate_workflow_id(path)
        safe_new = validate_workflow_id(new_path)
        moves = self._renamed_workflow_moves(old_folder, safe_old, safe_new)
        identities = [identity for move in moves for identity in move]
        with self.workflow_mutations(identities):
            self._validate_moved_workflows(moves)
            self._reserve_workflow_generations(identities)
            self._ensure_directory_durable(new_folder.parent)
            old_folder.rename(new_folder)
            if old_folder.parent.exists():
                self._fsync_directory(old_folder.parent)
            self._fsync_directory(new_folder.parent)
            self._rewrite_moved_workflows(moves)
        return WorkflowFolderInfo(path=safe_new, display_name=safe_new.split("/")[-1])

    def create_workflow(self, data: WorkflowCreate) -> WorkflowInfo:
        with self.workflow_structure_mutation(), self.workflow_mutation(data.name):
            self.ensure_workflow_mutations_available()
            path = self._path_for(data.name)
            if path.exists() or self._workflow_dir(data.name).exists():
                raise FileExistsError(data.name)
            raw = self._empty_raw(data)
            self._reserve_workflow_generations([data.name])
            self._write_raw(data.name, raw)
            return self._metadata_from_raw(data.name, self._read_raw(data.name), path)

    def install_workflow_templates(
        self,
        templates: list[WorkflowTemplate],
    ) -> list[WorkflowInfo]:
        """Atomically publish a set of prevalidated bundled workflow templates."""

        if not templates:
            return []
        names = [self._validate_name(template.workflow_id) for template in templates]
        if len(names) != len(set(names)):
            raise ValueError("Workflow template identities must be unique")

        with self.workflow_structural_mutations(names):
            self.ensure_workflow_mutations_available()
            root_existed = self.root_dir.exists()
            for name in names:
                if self._has_name_collision(name):
                    raise FileExistsError(name)

            prepared: list[tuple[str, Path, Path]] = []
            published: list[Path] = []
            created_parents: set[Path] = set()
            try:
                for name, template in zip(names, templates, strict=True):
                    self.validate_containment(name, template.document.graph)
                    document = template.document.model_copy(
                        update={
                            "artifact_hash": artifact_hash(template.document.graph, []),
                        }
                    )
                    destination = self._workflow_dir(name)
                    parent_existed = destination.parent.exists()
                    self._ensure_directory_durable(destination.parent)
                    if not parent_existed:
                        created_parents.add(destination.parent)
                    staging = Path(
                        tempfile.mkdtemp(
                            dir=str(destination.parent),
                            prefix=f".{destination.name}.demo.",
                        )
                    )
                    workflow_path = staging / "workflow.json"
                    with workflow_path.open("w", encoding="utf-8") as handle:
                        json.dump(
                            document.model_dump(mode="json", by_alias=True, exclude_none=True),
                            handle,
                            indent=2,
                            sort_keys=True,
                        )
                        handle.write("\n")
                        handle.flush()
                        os.fsync(handle.fileno())

                    tools_dir = staging / "tools"
                    tools_dir.mkdir()
                    for filename, content in sorted(template.tool_files.items()):
                        relative = Path(filename)
                        if (
                            relative.is_absolute()
                            or len(relative.parts) != 1
                            or relative.suffix != ".py"
                            or relative.name.startswith(".")
                        ):
                            raise ValueError(f"Invalid bundled tool filename: {filename!r}")
                        tool_path = tools_dir / relative
                        with tool_path.open("wb") as handle:
                            handle.write(content)
                            handle.flush()
                            os.fsync(handle.fileno())
                    self._fsync_directory(tools_dir)
                    self._fsync_directory(staging)
                    prepared.append((name, staging, destination))

                self._reserve_workflow_generations(names)
                for _, staging, destination in prepared:
                    os.replace(staging, destination)
                    published.append(destination)
                    self._fsync_directory(destination.parent)
            except Exception:
                for path in reversed(published):
                    shutil.rmtree(path, ignore_errors=True)
                for _, staging, _ in prepared:
                    shutil.rmtree(staging, ignore_errors=True)
                for parent in sorted(
                    created_parents,
                    key=lambda path: len(path.parts),
                    reverse=True,
                ):
                    try:
                        parent.rmdir()
                    except OSError:
                        pass
                if not root_existed:
                    try:
                        self.root_dir.rmdir()
                    except OSError:
                        pass
                raise

            return [
                self._metadata_from_raw(name, self._read_raw(name), self._path_for(name))
                for name in names
            ]

    @_identity_locked
    def get_workflow(self, name: str) -> WorkflowFile:
        path = self._existing_path_for(name)
        self.ensure_workflow_format_current(name)
        document = WorkflowDocument.model_validate(self._read_raw(name))
        self.tool_registry.watch_owned_sources(self._workflow_dir(name), document.graph)
        translation = graph_state_to_lib_dict(
            document.graph,
            self.tool_registry,
        )
        return WorkflowFile(
            info=self._metadata_from_raw(
                name,
                document.model_dump(mode="json", by_alias=True),
                path,
            ),
            graph=document.graph,
            artifact_hash=artifact_hash(
                document.graph,
                OwnedWorkflowSources(self._workflow_dir(name)).collect_for_graph(document.graph),
            ),
            authoring_source=document.authoring_source,
            missing_packages=_detect_missing_packages(
                translation.lib_dict,
                self.tool_registry,
            ),
            missing_tools=_detect_missing_tools(translation.lib_dict, self.tool_registry),
        )

    @_identity_locked
    def viewing_requirements(self, name: str) -> ViewingRequirementsManifest:
        """Inspect recursive viewing readiness without installing packages."""

        from bioimageflow import Workflow

        document = WorkflowDocument.model_validate(self._read_raw(name))
        library = graph_state_to_lib_dict(document.graph, self.tool_registry).lib_dict
        workflow, _errors = Workflow.from_dict(
            library,
            storage_path=self.get_storage_path(name),
            validate_only=True,
            partial=True,
            auto_install=False,
        )
        return ViewingRequirementsManifest.model_validate(workflow.viewing_requirements().to_dict())

    @_identity_locked
    def save_workflow(self, name: str, data: WorkflowSaveBody) -> WorkflowInfo:
        self.ensure_workflow_mutations_available()
        self.ensure_workflow_format_current(name)
        path = self._existing_path_for(name)
        self.validate_containment(name, data.graph)
        current = WorkflowDocument.model_validate(self._read_raw(name))
        sources = OwnedWorkflowSources(self._workflow_dir(name)).collect_for_graph(data.graph)
        document = current.model_copy(
            update={
                "graph": data.graph,
                "owned_source_ids": sorted(referenced_source_ids(data.graph)),
                "artifact_hash": artifact_hash(data.graph, sources),
            }
        )
        self._write_raw(name, document.model_dump(mode="json", by_alias=True))
        return self._metadata_from_raw(name, self._read_raw(name), path)

    def delete_workflow(
        self,
        name: str,
        *,
        expected_identity_generation: int | None = None,
    ) -> int:
        with self.workflow_structural_mutations([name]):
            self.ensure_workflow_mutations_available()
            path = self._path_for(name)
            if not path.exists():
                raise FileNotFoundError(name)
            current_generation = self.workflow_generation(name)
            if (
                expected_identity_generation is not None
                and current_generation != expected_identity_generation
            ):
                raise WorkflowIdentityGenerationConflictError(
                    name,
                    expected_identity_generation,
                    current_generation,
                )
            generation = self._reserve_workflow_generations([name])[name]
            try:
                shutil.rmtree(path.parent)
            except Exception:
                if path.exists():
                    raise
                logger.exception(
                    "Workflow '%s' was removed but directory cleanup reported failure at %s",
                    name,
                    path.parent,
                )
            return generation

    def patch_workflow(
        self,
        name: str,
        patch: WorkflowUpdate,
        *,
        move_operation_id: UUID | None = None,
    ) -> WorkflowInfo:
        new_name = self._updated_workflow_name(name, patch)
        with self.workflow_structural_mutations([name, new_name]):
            if patch.action != "duplicate" and new_name != self._validate_name(name):
                journal = self._require_prepared_workflow_move(
                    move_operation_id,
                    operation_kind="direct_workflow_move",
                    source_path=self._validate_name(name),
                    destination_path=new_name,
                )
                self._validate_prepared_move_execution(
                    journal,
                    [(self._validate_name(name), new_name)],
                    patches={self._validate_name(name): patch},
                )
            else:
                self.ensure_workflow_mutations_available()
                if move_operation_id is not None:
                    raise WorkflowMoveRecoveryError(
                        "Only an identity-changing workflow patch accepts a move operation"
                    )
            info = self._patch_workflow_locked(name, patch, new_name)
            if move_operation_id is not None:
                self.mark_workflow_move_phase(
                    move_operation_id,
                    "artifacts_rewritten",
                )
            return info

    def plan_workflow_update_moves(
        self,
        name: str,
        patch: WorkflowUpdate,
    ) -> list[WorkflowIdentityMovePlan]:
        """Capture a direct root identity move without treating duplication as a move."""

        with self.workflow_structure_mutation():
            safe_name = self._validate_name(name)
            new_name = self._updated_workflow_name(safe_name, patch)
            if patch.action == "duplicate" or new_name == safe_name:
                return []
            self._existing_path_for(safe_name)
            return self._identity_move_plans([(safe_name, new_name)])

    def _updated_workflow_name(self, name: str, patch: WorkflowUpdate) -> str:
        if patch.action == "duplicate":
            if patch.new_name is None:
                raise ValueError("new_name is required for duplicate")
            return self._validate_name(patch.new_name)

        old_folder = self._folder_name(name)
        if patch.new_id is not None:
            return self._validate_name(patch.new_id)
        if patch.new_name is not None:
            new_leaf = self._leaf_name(patch.new_name)
            target_folder = patch.folder if patch.folder is not None else old_folder
            new_name = f"{target_folder}/{new_leaf}" if target_folder else new_leaf
            return self._validate_name(new_name)
        if patch.folder is not None:
            new_leaf = self._leaf_name(name)
            new_name = f"{patch.folder}/{new_leaf}" if patch.folder else new_leaf
            return self._validate_name(new_name)
        return self._validate_name(name)

    def _patch_workflow_locked(
        self,
        name: str,
        patch: WorkflowUpdate,
        new_name: str,
    ) -> WorkflowInfo:
        path = self._existing_path_for(name)
        if (
            patch.expected_identity_generation is not None
            and self.workflow_generation(name) != patch.expected_identity_generation
        ):
            raise WorkflowIdentityGenerationConflictError(
                name, patch.expected_identity_generation, self.workflow_generation(name)
            )
        raw = self._read_raw(name)
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        if patch.action == "duplicate":
            new_path = self._path_for(new_name)
            if new_path.exists() or self._workflow_dir(new_name).exists():
                raise FileExistsError(new_name)
            duplicate = cast(dict[str, Any], json.loads(json.dumps(raw)))
            duplicate_metadata = duplicate.setdefault("metadata", {})
            if isinstance(duplicate_metadata, dict):
                if patch.description is not None:
                    duplicate_metadata["description"] = patch.description
            duplicate_graph = patch.graph or GraphState.model_validate(duplicate["graph"])
            duplicate_graph = duplicate_graph.model_copy(
                update={
                    "name": self._leaf_name(new_name),
                    "display_name": patch.display_name or self._leaf_name(new_name),
                }
            )
            self.validate_containment(new_name, duplicate_graph)
            try:
                source_records = OwnedWorkflowSources(self._workflow_dir(name)).collect_for_graph(
                    duplicate_graph
                )
            except FileNotFoundError as exc:
                raise ValueError("A workflow-local source required by the copy is missing") from exc
            duplicate["graph"] = duplicate_graph.model_dump(mode="json", by_alias=True)
            duplicate["owned_source_ids"] = sorted(referenced_source_ids(duplicate_graph))
            duplicate["artifact_hash"] = artifact_hash(duplicate_graph, source_records)
            destination = self._workflow_dir(new_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".workflow-copy-", dir=destination.parent))
            try:
                destination_sources = OwnedWorkflowSources(staging)
                destination_sources.publish(destination_sources.stage(source_records))
                old_tools = self._workflow_tools_dir(name)
                if old_tools.exists():
                    shutil.copytree(old_tools, staging / "tools", dirs_exist_ok=True)
                with (staging / "workflow.json").open("w", encoding="utf-8") as handle:
                    json.dump(duplicate, handle, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                self._fsync_directory(staging)
                self._reserve_workflow_generations([new_name])
                os.replace(staging, destination)
                self._fsync_directory(destination.parent)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            return self._metadata_from_raw(new_name, self._read_raw(new_name), new_path)

        if new_name != name and self._has_name_collision(new_name):
            raise FileExistsError(new_name)
        if new_name != name:
            self._validate_moved_workflow_drafts([(name, new_name)])
            self._reserve_workflow_generations([name, new_name])

        if patch.display_name is not None:
            graph = GraphState.model_validate(raw["graph"]).model_copy(
                update={"display_name": patch.display_name}
            )
            raw["graph"] = graph.model_dump(mode="json", by_alias=True)
            source_records = OwnedWorkflowSources(self._workflow_dir(name)).collect_for_graph(graph)
            raw["artifact_hash"] = artifact_hash(graph, source_records)
        if patch.description is not None:
            metadata["description"] = patch.description
        raw["metadata"] = metadata
        if new_name != name:
            destination = self._workflow_dir(new_name)
            self._ensure_directory_durable(destination.parent)
            path.parent.rename(destination)
            if path.parent.parent.exists():
                self._fsync_directory(path.parent.parent)
            self._fsync_directory(destination.parent)
            normalize_workflow_draft_identity(destination, new_name)
        self._write_raw(new_name, raw)
        if new_name != name:
            self._rewrite_moved_source_provenance({name: new_name})
        return self._metadata_from_raw(
            new_name,
            self._read_raw(new_name),
            self._path_for(new_name),
        )

    @_identity_locked
    def rebind_versions(self, name: str) -> WorkflowFile:
        self.ensure_workflow_mutations_available()
        document = WorkflowDocument.model_validate(self._read_raw(name))
        translation = graph_state_to_lib_dict(document.graph, self.tool_registry)
        rebound = rebind_lib_dict_versions(translation.lib_dict, self.tool_registry)
        graph = lib_dict_to_graph_state(rebound)
        # The library grammar has no GUI state. Preserve the accepted graph's
        # presentation recursively while replacing only dependency identities.
        def preserve_presentation(
            rebound_graph: GraphState, accepted_graph: GraphState
        ) -> GraphState:
            accepted_nodes = {node.id: node for node in accepted_graph.nodes}
            nodes = []
            for node in rebound_graph.nodes:
                accepted = accepted_nodes[node.id]
                updates: dict[str, Any] = {
                    "position": accepted.position,
                    "collapsed": accepted.collapsed,
                    "resources": accepted.resources,
                    "name": accepted.name,
                }
                if isinstance(node, WorkflowNodeState) and isinstance(
                    accepted, WorkflowNodeState
                ):
                    updates["workflow"] = preserve_presentation(
                        node.workflow, accepted.workflow
                    )
                nodes.append(node.model_copy(update=updates))
            return rebound_graph.model_copy(update={"nodes": nodes})

        graph = preserve_presentation(graph, document.graph)
        sources = OwnedWorkflowSources(self._workflow_dir(name)).collect_for_graph(graph)
        updated = document.model_copy(
            update={"graph": graph, "artifact_hash": artifact_hash(graph, sources)}
        )
        self._write_raw(name, updated.model_dump(mode="json", by_alias=True))
        return self.get_workflow(name)

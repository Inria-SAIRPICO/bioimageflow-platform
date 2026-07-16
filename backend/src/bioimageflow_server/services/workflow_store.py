"""Filesystem-backed workflow persistence service."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import ValidationError

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import (
    ExportedWorkflow,
    LocalToolReference,
    RequiredPackage,
    WorkflowCreate,
    WorkflowExportDocument,
    WorkflowFile,
    WorkflowFolderDelete,
    WorkflowFolderInfo,
    WorkflowInfo,
    WorkflowImportResponse,
    WorkflowSaveBody,
    WorkflowUpdate,
    validate_workflow_id,
)
from bioimageflow_server.models.workflow_draft import WorkflowDraftResponse
from bioimageflow_server.services.graph_translator import (
    collect_required_packages,
    _detect_missing_packages,
    _detect_missing_tools,
    graph_state_to_persisted_sections,
    lib_dict_to_graph_state,
    rebind_lib_dict_versions,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_archive import BioImageFlowWorkflowArchiveAdapter


class WorkflowArchiveError(ValueError):
    """Raised when a workflow archive cannot be imported or exported."""


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


_WORKFLOW_GENERATION_LEDGER_VERSION = 1
_WORKFLOW_GENERATION_LEDGER_NAME = "workflow-identity-generations.json"
logger = logging.getLogger(__name__)


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

    def export_archive(self, workflow_path: Path, archive_path: Path) -> None: ...

    def read_archive(
        self,
        archive_path: Path,
        *,
        extract_to: Path | None = None,
    ) -> dict[str, Any]: ...


def _identity_locked(method: Any) -> Any:
    """Serialize one workflow identity across saved and draft mutations."""

    @wraps(method)
    def wrapped(self: "WorkflowStoreService", name: str, *args: Any, **kwargs: Any) -> Any:
        with self.workflow_mutation(name):
            return method(self, name, *args, **kwargs)

    return wrapped


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
        os.replace(tmp_name, draft_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    return normalized


def _merge_export_requirements(
    primary: tuple[list[RequiredPackage], list[LocalToolReference]],
    fallback: tuple[list[RequiredPackage], list[LocalToolReference]],
) -> tuple[list[RequiredPackage], list[LocalToolReference]]:
    package_map = {
        (package.name, package.version): package for package in [*primary[0], *fallback[0]]
    }
    local_map: dict[str, list[str]] = {}
    for tool in [*primary[1], *fallback[1]]:
        node_ids = local_map.setdefault(tool.tool_name, [])
        for node_id in tool.node_ids:
            if node_id not in node_ids:
                node_ids.append(node_id)
    return (
        [package_map[key] for key in sorted(package_map)],
        [
            LocalToolReference(tool_name=tool_name, node_ids=node_ids)
            for tool_name, node_ids in sorted(local_map.items())
        ],
    )


def _graph_nodes_missing_from_library(
    graph: dict[str, Any],
    library: dict[str, Any],
) -> dict[str, Any]:
    library_node_ids = {
        str(node.get("id") or node.get("name"))
        for node in library.get("nodes", [])
        if isinstance(node, dict) and (node.get("id") or node.get("name"))
    }
    graph_nodes = graph.get("nodes", [])
    if not isinstance(graph_nodes, list) or not library_node_ids:
        return graph
    graph_fallback = dict(graph)
    graph_fallback["nodes"] = [
        node
        for node in graph_nodes
        if not isinstance(node, dict)
        or str(node.get("id") or node.get("name")) not in library_node_ids
    ]
    return graph_fallback


class WorkflowStoreService:
    """Manage workflow JSON files under one root directory."""

    def __init__(
        self,
        root_dir: Path,
        tool_registry: ToolRegistryService,
        *,
        storage_base_dir: Path | None = None,
        archive_adapter: WorkflowArchiveAdapter | None = None,
    ) -> None:
        self.root_dir = self._normalize_storage_path(root_dir)
        self.workspace_dir = (
            self.root_dir.parent if self.root_dir.name == "workflows" else self.root_dir
        )
        self.tool_registry = tool_registry
        self.storage_base_dir = self._normalize_storage_path(
            storage_base_dir or self.root_dir / "outputs"
        )
        self.archive_adapter = archive_adapter or BioImageFlowWorkflowArchiveAdapter()
        self._workflow_generation_ledger_path = (
            self.workspace_dir / ".bioimageflow" / _WORKFLOW_GENERATION_LEDGER_NAME
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
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def _ensure_workflow_layout(self, name: str) -> None:
        self._workflow_tools_dir(name).mkdir(parents=True, exist_ok=True)

    def _existing_path_for(self, name: str) -> Path:
        path = self._path_for(name)
        if path.exists():
            return path
        raise FileNotFoundError(name)

    def _managed_storage_path(self, name: str) -> Path:
        return self.storage_base_dir.joinpath(*self._validate_name(name).split("/"))

    def _storage_path_string(self, path: str | Path) -> str:
        return str(self._normalize_storage_path(path))

    def _has_name_collision(self, name: str) -> bool:
        return (
            self._path_for(name).exists()
            or self._workflow_dir(name).exists()
            or self._managed_storage_path(name).exists()
        )

    def _is_managed_storage_path(self, name: str, storage_path: str | None) -> bool:
        if not storage_path:
            return True
        return Path(storage_path) == self._managed_storage_path(name)

    def _move_managed_storage(self, old_name: str, new_name: str) -> str:
        old_storage = self._managed_storage_path(old_name)
        new_storage = self._managed_storage_path(new_name)
        if old_storage == new_storage:
            return str(new_storage)
        if new_storage.exists():
            raise FileExistsError(new_name)
        if old_storage.exists():
            new_storage.parent.mkdir(parents=True, exist_ok=True)
            old_storage.rename(new_storage)
        return str(new_storage)

    def _delete_managed_storage_best_effort(self, name: str) -> None:
        managed_path = self._managed_storage_path(name)
        if not managed_path.exists() or not managed_path.is_relative_to(self.storage_base_dir):
            return
        try:
            shutil.rmtree(managed_path)
        except Exception:
            logger.exception(
                "Workflow '%s' was deleted but managed output cleanup failed at %s",
                name,
                managed_path,
            )

    def _set_workflow_storage_path(self, raw: dict[str, Any], storage_path: str) -> None:
        workflow_data = raw.get("workflow", {})
        if not isinstance(workflow_data, dict):
            workflow_data = {}
            raw["workflow"] = workflow_data
        config = workflow_data.get("config", {})
        if not isinstance(config, dict):
            config = {}
        config["storage_path"] = storage_path
        workflow_data["config"] = config

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
        current = path
        while current != self.root_dir:
            if (current / "workflow.json").exists():
                return True
            current = current.parent
        return False

    def _rewrite_moved_workflow_metadata(self, old_name: str, new_name: str) -> None:
        if old_name == new_name:
            return
        path = self._path_for(new_name)
        normalize_workflow_draft_identity(path.parent, new_name)
        raw = json.loads(path.read_text(encoding="utf-8"))
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        if self._is_managed_storage_path(
            old_name,
            cast(str | None, metadata.get("storage_path")),
        ):
            metadata["storage_path"] = self._move_managed_storage(old_name, new_name)
        raw["metadata"] = metadata
        storage_path = metadata.get("storage_path")
        if isinstance(storage_path, str) and storage_path:
            self._set_workflow_storage_path(raw, storage_path)
        self._write_raw(new_name, raw)

    def _ensure_moved_workflow_storage_available(
        self,
        moves: list[tuple[str, str]],
    ) -> None:
        self._validate_moved_workflow_drafts(moves)
        for old_name, new_name in moves:
            if old_name == new_name:
                continue
            raw = self._read_raw(old_name)
            metadata = raw.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            if not self._is_managed_storage_path(
                old_name,
                cast(str | None, metadata.get("storage_path")),
            ):
                continue
            new_storage = self._managed_storage_path(new_name)
            if new_storage.exists() and new_storage != self._managed_storage_path(old_name):
                raise FileExistsError(new_name)

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

    @staticmethod
    def _renamed_child_path(old_name: str, old_prefix: str, new_prefix: str) -> str:
        suffix = old_name[len(old_prefix) :]
        return f"{new_prefix}{suffix}" if new_prefix else suffix.lstrip("/")

    @staticmethod
    def _promoted_child_path(old_name: str, removed_prefix: str, parent_prefix: str) -> str:
        suffix = old_name[len(removed_prefix) :].lstrip("/")
        return f"{parent_prefix}/{suffix}" if parent_prefix else suffix

    def _metadata_from_raw(
        self,
        name: str,
        raw: dict[str, Any],
        path: Path,
    ) -> WorkflowInfo:
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        last_modified = datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=UTC,
        ).isoformat()
        return WorkflowInfo(
            id=name,
            name=self._leaf_name(name),
            folder=self._folder_name(name),
            display_name=str(metadata.get("display_name") or name),
            description=cast(str | None, metadata.get("description")),
            storage_path=cast(str | None, metadata.get("storage_path")),
            output_path=cast(str | None, metadata.get("storage_path")),
            workspace_path=str(self.workspace_dir),
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
        return data

    def get_storage_path(self, name: str) -> Path:
        """Return the storage root recorded for a workflow."""
        raw = self._read_raw(name)
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        storage_path = metadata.get("storage_path")
        if isinstance(storage_path, str) and storage_path:
            return self._normalize_storage_path(storage_path)
        return self._managed_storage_path(name)

    def _write_raw(self, name: str, raw: dict[str, Any]) -> None:
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
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def _empty_raw(self, data: WorkflowCreate) -> dict[str, Any]:
        graph = GraphState(nodes=[], edges=[])
        storage_path = self._storage_path_string(
            data.storage_path or self._managed_storage_path(data.name)
        )
        metadata = {
            "display_name": data.display_name or data.name,
            "description": data.description,
            "storage_path": storage_path,
        }
        graph_section, workflow_section, gui_section, _ = graph_state_to_persisted_sections(
            graph,
            self.tool_registry,
            storage_path=Path(metadata["storage_path"]),
        )
        return {
            "graph": graph_section,
            "workflow": workflow_section,
            "gui": gui_section,
            "metadata": metadata,
        }

    def suggest_name(self, base_name: str) -> str:
        base = self._validate_name(base_name)
        candidate = base
        suffix = 2
        while self._has_name_collision(candidate):
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @_identity_locked
    def export_workflow(self, name: str) -> WorkflowExportDocument:
        path = self._existing_path_for(name)
        raw = self._read_raw(name)
        info = self._metadata_from_raw(name, raw, path)
        graph = raw.get("graph", {})
        library = raw.get("workflow", {})
        gui = raw.get("gui", {})
        metadata = raw.get("metadata", {})
        if not isinstance(graph, dict):
            graph = {}
        if not isinstance(library, dict):
            library = {}
        if not isinstance(gui, dict):
            gui = {}
        if not isinstance(metadata, dict):
            metadata = {}
        required_packages, local_tools = _merge_export_requirements(
            collect_required_packages(library, self.tool_registry),
            collect_required_packages(
                _graph_nodes_missing_from_library(graph, library),
                self.tool_registry,
            ),
        )
        return WorkflowExportDocument(
            exported_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            workflow=ExportedWorkflow(
                name=info.name,
                display_name=info.display_name,
                description=info.description,
                storage_path=info.storage_path,
                graph=cast(dict[str, Any], json.loads(json.dumps(graph))),
                library=cast(dict[str, Any], json.loads(json.dumps(library))),
                gui=cast(dict[str, Any], json.loads(json.dumps(gui))),
                metadata=cast(dict[str, Any], json.loads(json.dumps(metadata))),
            ),
            required_packages=required_packages,
            local_tools=local_tools,
        )

    def export_workflow_archive(self, name: str) -> tuple[str, bytes]:
        workflow_path = self._existing_path_for(name)
        filename = f"{self._validate_name(name)}.bioimageflow.zip"
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = Path(tmp_dir) / filename
            try:
                self.archive_adapter.export_archive(workflow_path, archive_path)
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
        imported_name = self._validate_name(
            name_override or self._archive_name_from_filename(filename)
        )
        with self.workflow_structure_mutation(), self.workflow_mutation(imported_name):
            if self._has_name_collision(imported_name):
                raise FileExistsError(imported_name)
            self._reserve_workflow_generations([imported_name])
            return self._import_workflow_archive_locked(
                raw_archive,
                filename=filename,
                imported_name=imported_name,
            )

    def _import_workflow_archive_locked(
        self,
        raw_archive: bytes,
        *,
        filename: str | None,
        imported_name: str,
    ) -> WorkflowImportResponse:
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = Path(tmp_dir) / (filename or f"{imported_name}.bioimageflow.zip")
            archive_path.write_bytes(raw_archive)
            try:
                library = self.archive_adapter.read_archive(
                    archive_path,
                    extract_to=self._workflow_dir(imported_name),
                )
            except Exception as exc:
                workflow_dir = self._workflow_dir(imported_name)
                if workflow_dir.exists():
                    shutil.rmtree(workflow_dir)
                raise WorkflowArchiveError(str(exc)) from exc
            if not isinstance(library, dict):
                workflow_dir = self._workflow_dir(imported_name)
                if workflow_dir.exists():
                    shutil.rmtree(workflow_dir)
                raise WorkflowArchiveError("Workflow archive did not contain a workflow object")
            graph = lib_dict_to_graph_state(library, None).model_dump(mode="json")
            document = WorkflowExportDocument(
                exported_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                workflow=ExportedWorkflow(
                    name=imported_name,
                    display_name=imported_name,
                    description=None,
                    storage_path=None,
                    graph=graph,
                    library=library,
                    gui={"nodes": {}},
                    metadata={},
                ),
                required_packages=[],
                local_tools=[],
            )
            try:
                return self._persist_import_workflow(document, imported_name)
            except Exception:
                workflow_dir = self._workflow_dir(imported_name)
                if workflow_dir.exists():
                    shutil.rmtree(workflow_dir)
                raise

    def import_workflow(
        self,
        document: WorkflowExportDocument,
        *,
        name_override: str | None = None,
    ) -> WorkflowImportResponse:
        imported_name = self._validate_name(name_override or document.workflow.name)
        with self.workflow_structure_mutation(), self.workflow_mutation(imported_name):
            if self._has_name_collision(imported_name):
                raise FileExistsError(imported_name)
            GraphState.model_validate(document.workflow.graph)
            self._reserve_workflow_generations([imported_name])
            return self._persist_import_workflow(document, imported_name)

    def _persist_import_workflow(
        self,
        document: WorkflowExportDocument,
        imported_name: str,
    ) -> WorkflowImportResponse:
        GraphState.model_validate(document.workflow.graph)
        graph = cast(dict[str, Any], json.loads(json.dumps(document.workflow.graph)))
        library = cast(
            dict[str, Any],
            json.loads(json.dumps(document.workflow.library)),
        )
        gui = cast(dict[str, Any], json.loads(json.dumps(document.workflow.gui)))
        metadata = cast(
            dict[str, Any],
            json.loads(json.dumps(document.workflow.metadata)),
        )
        metadata["display_name"] = document.workflow.display_name or imported_name
        metadata["description"] = document.workflow.description
        metadata["storage_path"] = str(self._managed_storage_path(imported_name))

        raw = {
            "graph": graph,
            "workflow": library,
            "gui": gui,
            "metadata": metadata,
        }
        self._set_workflow_storage_path(raw, metadata["storage_path"])
        self._write_raw(imported_name, raw)
        loaded = self.get_workflow(imported_name)
        return WorkflowImportResponse(
            info=loaded.info,
            missing_packages=loaded.missing_packages,
            missing_tools=loaded.missing_tools,
        )

    def list_workflows(self) -> list[WorkflowInfo]:
        if not self.root_dir.exists():
            return []
        workflows: list[WorkflowInfo] = []
        names = {
            path.parent.relative_to(self.root_dir).as_posix()
            for path in self.root_dir.glob("**/workflow.json")
            if not path.name.startswith(".")
            and not self._is_inside_workflow_dir(path.parent.parent)
        }
        for name in sorted(names):
            if name.startswith("."):
                continue
            try:
                with self.workflow_mutation(name):
                    path = self._existing_path_for(name)
                    raw = self._read_raw(name)
                    workflows.append(self._metadata_from_raw(name, raw, path))
            except (OSError, json.JSONDecodeError, ValidationError, ValueError):
                continue
        return workflows

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

    def delete_folder(
        self,
        path: str,
        policy: WorkflowFolderDelete | str = "empty",
    ) -> None:
        with self.workflow_structure_mutation():
            self._delete_folder_locked(path, policy)

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
                for workflow_name in workflow_names:
                    self._delete_managed_storage_best_effort(workflow_name)
            return
        if children and policy_name == "move_children_up":
            safe_path = validate_workflow_id(path)
            parent_prefix, _, _ = safe_path.rpartition("/")
            moves = [
                (name, self._promoted_child_path(name, safe_path, parent_prefix))
                for name in self._workflow_names_under_folder(folder)
            ]
            identities = [identity for move in moves for identity in move]
            with self.workflow_mutations(identities):
                children = list(folder.iterdir())
                self._ensure_moved_workflow_storage_available(moves)
                for child in children:
                    destination = folder.parent / child.name
                    if destination.exists():
                        raise FileExistsError(destination.name)
                self._reserve_workflow_generations(identities)
                for child in children:
                    child.rename(folder.parent / child.name)
                self._rewrite_moved_workflows(moves)
        folder.rmdir()

    def rename_folder(self, path: str, new_path: str) -> WorkflowFolderInfo:
        with self.workflow_structure_mutation():
            return self._rename_folder_locked(path, new_path)

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
        moves = [
            (name, self._renamed_child_path(name, safe_old, safe_new))
            for name in self._workflow_names_under_folder(old_folder)
        ]
        identities = [identity for move in moves for identity in move]
        with self.workflow_mutations(identities):
            self._ensure_moved_workflow_storage_available(moves)
            self._reserve_workflow_generations(identities)
            new_folder.parent.mkdir(parents=True, exist_ok=True)
            old_folder.rename(new_folder)
            self._rewrite_moved_workflows(moves)
        return WorkflowFolderInfo(path=safe_new, display_name=safe_new.split("/")[-1])

    def create_workflow(self, data: WorkflowCreate) -> WorkflowInfo:
        with self.workflow_structure_mutation(), self.workflow_mutation(data.name):
            path = self._path_for(data.name)
            if path.exists() or self._workflow_dir(data.name).exists():
                raise FileExistsError(data.name)
            if data.storage_path is None and self._managed_storage_path(data.name).exists():
                raise FileExistsError(data.name)
            raw = self._empty_raw(data)
            self._reserve_workflow_generations([data.name])
            self._write_raw(data.name, raw)
            return self._metadata_from_raw(data.name, self._read_raw(data.name), path)

    @_identity_locked
    def get_workflow(self, name: str) -> WorkflowFile:
        path = self._existing_path_for(name)
        raw = self._read_raw(name)
        workflow_data = raw.get("workflow", {})
        if not isinstance(workflow_data, dict):
            workflow_data = {}
        gui_data = raw.get("gui", {})
        if not isinstance(gui_data, dict):
            gui_data = {}
        graph_data = raw.get("graph")
        graph = (
            GraphState.model_validate(graph_data)
            if graph_data is not None
            else lib_dict_to_graph_state(workflow_data, gui_data)
        )
        return WorkflowFile(
            info=self._metadata_from_raw(name, raw, path),
            graph=graph,
            gui=gui_data,
            missing_packages=_detect_missing_packages(
                workflow_data,
                self.tool_registry,
            ),
            missing_tools=_detect_missing_tools(workflow_data, self.tool_registry),
        )

    @_identity_locked
    def save_workflow(self, name: str, data: WorkflowSaveBody) -> WorkflowInfo:
        path = self._existing_path_for(name)
        raw = self._read_raw(name)
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        storage_path = metadata.get("storage_path")
        if not isinstance(storage_path, str) or not storage_path:
            storage_path = str(self._managed_storage_path(name))
            metadata["storage_path"] = storage_path
        graph_section, workflow_section, gui_section, _ = graph_state_to_persisted_sections(
            data.graph,
            self.tool_registry,
            storage_path=Path(storage_path),
        )
        self._write_raw(
            name,
            {
                "graph": graph_section,
                "workflow": workflow_section,
                "gui": gui_section,
                "metadata": metadata,
            },
        )
        return self._metadata_from_raw(name, self._read_raw(name), path)

    def delete_workflow(
        self,
        name: str,
        *,
        expected_identity_generation: int | None = None,
    ) -> int:
        with self.workflow_structural_mutations([name]):
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
            self._delete_managed_storage_best_effort(name)
            return generation

    def patch_workflow(self, name: str, patch: WorkflowUpdate) -> WorkflowInfo:
        new_name = self._updated_workflow_name(name, patch)
        with self.workflow_structural_mutations([name, new_name]):
            return self._patch_workflow_locked(name, patch, new_name)

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
        raw = self._read_raw(name)
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        if patch.action == "duplicate":
            new_path = self._path_for(new_name)
            if new_path.exists() or self._workflow_dir(new_name).exists():
                raise FileExistsError(new_name)
            if patch.storage_path is None and self._managed_storage_path(new_name).exists():
                raise FileExistsError(new_name)
            duplicate = cast(dict[str, Any], json.loads(json.dumps(raw)))
            duplicate_metadata = duplicate.setdefault("metadata", {})
            if isinstance(duplicate_metadata, dict):
                duplicate_metadata["display_name"] = patch.display_name or new_name
                if patch.description is not None:
                    duplicate_metadata["description"] = patch.description
                duplicate_metadata["storage_path"] = self._storage_path_string(
                    patch.storage_path or self._managed_storage_path(new_name)
                )
                self._set_workflow_storage_path(
                    duplicate,
                    duplicate_metadata["storage_path"],
                )
            self._reserve_workflow_generations([new_name])
            self._write_raw(new_name, duplicate)
            old_tools = self._workflow_tools_dir(name)
            new_tools = self._workflow_tools_dir(new_name)
            if old_tools.exists():
                if new_tools.exists():
                    shutil.rmtree(new_tools)
                shutil.copytree(old_tools, new_tools)
            return self._metadata_from_raw(new_name, self._read_raw(new_name), new_path)

        if new_name != name and self._has_name_collision(new_name):
            raise FileExistsError(new_name)
        if new_name != name:
            self._validate_moved_workflow_drafts([(name, new_name)])
            self._reserve_workflow_generations([name, new_name])

        if patch.display_name is not None:
            metadata["display_name"] = patch.display_name
        if patch.description is not None:
            metadata["description"] = patch.description
        if patch.storage_path is not None:
            metadata["storage_path"] = self._storage_path_string(patch.storage_path)
        elif new_name != name and self._is_managed_storage_path(
            name,
            cast(str | None, metadata.get("storage_path")),
        ):
            metadata["storage_path"] = self._move_managed_storage(name, new_name)
        raw["metadata"] = metadata
        storage_path = metadata.get("storage_path")
        if isinstance(storage_path, str) and storage_path:
            self._set_workflow_storage_path(raw, storage_path)
        if new_name != name:
            destination = self._workflow_dir(new_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            path.parent.rename(destination)
            normalize_workflow_draft_identity(destination, new_name)
        self._write_raw(new_name, raw)
        return self._metadata_from_raw(
            new_name,
            self._read_raw(new_name),
            self._path_for(new_name),
        )

    @_identity_locked
    def rebind_versions(self, name: str) -> WorkflowFile:
        raw = self._read_raw(name)
        workflow_data = raw.get("workflow", {})
        if not isinstance(workflow_data, dict):
            workflow_data = {}
        raw["workflow"] = rebind_lib_dict_versions(
            workflow_data,
            self.tool_registry,
        )
        self._write_raw(name, raw)
        return self.get_workflow(name)

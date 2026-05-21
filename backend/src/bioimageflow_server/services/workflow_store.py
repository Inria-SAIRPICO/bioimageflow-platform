"""Filesystem-backed workflow persistence service."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
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
    canonical_workflow_name,
    validate_workflow_id,
)
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


class WorkflowImportParseError(ValueError):
    """Raised when an import upload is not parseable JSON."""


class WorkflowImportValidationError(ValueError):
    """Raised when an import upload is JSON but not a supported export document."""


class WorkflowArchiveError(ValueError):
    """Raised when a workflow archive cannot be imported or exported."""


class WorkflowArchiveAdapter(Protocol):
    """Small boundary around BioImageFlow archive APIs."""

    def export_archive(self, workflow_path: Path, archive_path: Path) -> None: ...

    def read_archive(
        self,
        archive_path: Path,
        *,
        extract_to: Path | None = None,
    ) -> dict[str, Any]: ...


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
        self.workspace_dir = self.root_dir.parent if self.root_dir.name == "workflows" else self.root_dir
        self.tool_registry = tool_registry
        self.storage_base_dir = self._normalize_storage_path(
            storage_base_dir or self.root_dir / "outputs"
        )
        self.archive_adapter = archive_adapter or BioImageFlowWorkflowArchiveAdapter()

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

    def _legacy_path_for(self, name: str) -> Path:
        return self._legacy_paths_for(name)[0]

    def _legacy_paths_for(self, name: str) -> list[Path]:
        safe_name = self._validate_name(name)
        relative = Path(*safe_name.split("/"))
        return [
            self.root_dir / relative.with_suffix(".json"),
            self.root_dir / relative.with_suffix(".workflow.json"),
        ]

    def _legacy_path_exists(self, name: str) -> bool:
        return any(path.exists() for path in self._legacy_paths_for(name))

    def _ensure_workflow_layout(self, name: str) -> None:
        self._workflow_tools_dir(name).mkdir(parents=True, exist_ok=True)

    def _migrate_legacy_if_needed(self, name: str) -> Path:
        path = self._path_for(name)
        if path.exists():
            self._ensure_workflow_layout(name)
            return path
        legacy_path = next(
            (candidate for candidate in self._legacy_paths_for(name) if candidate.exists()),
            None,
        )
        if legacy_path is None:
            return path
        self._ensure_workflow_layout(name)
        os.replace(legacy_path, path)
        return path

    def _existing_path_for(self, name: str) -> Path:
        path = self._migrate_legacy_if_needed(name)
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
            or self._legacy_path_exists(name)
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
        for path in folder.glob("**/*.json"):
            if (
                path.name.startswith(".")
                or path.name == "workflow.json"
                or path.name.endswith(".workflow.json")
                or self._is_inside_workflow_dir(path.parent)
            ):
                continue
            names.add(path.relative_to(self.root_dir).with_suffix("").as_posix())
        for path in folder.glob("**/*.workflow.json"):
            if path.name.startswith(".") or self._is_inside_workflow_dir(path.parent):
                continue
            names.add(path.relative_to(self.root_dir).as_posix()[: -len(".workflow.json")])
        migrated_names: list[str] = []
        for name in sorted(names):
            try:
                if self._existing_path_for(name).exists():
                    migrated_names.append(name)
            except (OSError, json.JSONDecodeError, ValidationError, ValueError):
                continue
        return migrated_names

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

    def _rewrite_moved_workflows(self, moves: list[tuple[str, str]]) -> None:
        for old_name, new_name in moves:
            self._rewrite_moved_workflow_metadata(old_name, new_name)

    @staticmethod
    def _renamed_child_path(old_name: str, old_prefix: str, new_prefix: str) -> str:
        suffix = old_name[len(old_prefix):]
        return f"{new_prefix}{suffix}" if new_prefix else suffix.lstrip("/")

    @staticmethod
    def _promoted_child_path(old_name: str, removed_prefix: str, parent_prefix: str) -> str:
        suffix = old_name[len(removed_prefix):].lstrip("/")
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
        )

    def _read_raw(self, name: str) -> dict[str, Any]:
        path = self._existing_path_for(name)
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Workflow file {path} must contain a JSON object")
        return data

    def get_storage_path(self, name: str) -> Path:
        """Return the storage root recorded for a workflow.

        Legacy workflow files may not have metadata yet. In that case, use the
        managed per-workflow storage location without rewriting the file.
        """
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

    def parse_import_document(self, raw_json: bytes | str) -> WorkflowExportDocument:
        try:
            payload = json.loads(raw_json)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WorkflowImportParseError("Malformed JSON import file") from exc
        if not isinstance(payload, dict):
            raise WorkflowImportValidationError("Workflow import file must contain a JSON object")
        workflow = payload.get("workflow")
        if isinstance(workflow, dict) and "graph" not in workflow:
            library = workflow.get("library")
            gui = workflow.get("gui")
            if isinstance(library, dict):
                workflow["graph"] = lib_dict_to_graph_state(
                    library,
                    gui if isinstance(gui, dict) else None,
                ).model_dump(mode="json")
        try:
            return WorkflowExportDocument.model_validate(payload)
        except ValidationError as exc:
            raise WorkflowImportValidationError(str(exc)) from exc

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
        imported_name = self._validate_name(name_override or self._archive_name_from_filename(filename))
        if self._has_name_collision(imported_name):
            raise FileExistsError(imported_name)
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
        if self._has_name_collision(imported_name):
            raise FileExistsError(imported_name)
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
        names.update(
            path.relative_to(self.root_dir).with_suffix("").as_posix()
            for path in self.root_dir.glob("**/*.json")
            if not path.name.startswith(".")
            and path.name != "workflow.json"
            and not path.name.endswith(".workflow.json")
            and not self._is_inside_workflow_dir(path.parent)
        )
        names.update(
            path.relative_to(self.root_dir).as_posix()[: -len(".workflow.json")]
            for path in self.root_dir.glob("**/*.workflow.json")
            if not path.name.startswith(".")
            and not self._is_inside_workflow_dir(path.parent)
        )
        for name in sorted(names):
            if name.startswith("."):
                continue
            try:
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

    def delete_folder(
        self,
        path: str,
        policy: WorkflowFolderDelete | str = "empty",
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
            for workflow_name in self._workflow_names_under_folder(folder):
                managed_path = self._managed_storage_path(workflow_name)
                if managed_path.exists() and managed_path.is_relative_to(self.storage_base_dir):
                    shutil.rmtree(managed_path)
            shutil.rmtree(folder)
            return
        if children and policy_name == "move_children_up":
            safe_path = validate_workflow_id(path)
            parent_prefix, _, _ = safe_path.rpartition("/")
            moves = [
                (name, self._promoted_child_path(name, safe_path, parent_prefix))
                for name in self._workflow_names_under_folder(folder)
            ]
            children = list(folder.iterdir())
            self._ensure_moved_workflow_storage_available(moves)
            for child in children:
                destination = folder.parent / child.name
                if destination.exists():
                    raise FileExistsError(destination.name)
            for child in children:
                child.rename(folder.parent / child.name)
            self._rewrite_moved_workflows(moves)
        folder.rmdir()

    def rename_folder(self, path: str, new_path: str) -> WorkflowFolderInfo:
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
        self._ensure_moved_workflow_storage_available(moves)
        new_folder.parent.mkdir(parents=True, exist_ok=True)
        old_folder.rename(new_folder)
        self._rewrite_moved_workflows(moves)
        return WorkflowFolderInfo(path=safe_new, display_name=safe_new.split("/")[-1])

    def create_workflow(self, data: WorkflowCreate) -> WorkflowInfo:
        path = self._path_for(data.name)
        if (
            path.exists()
            or self._workflow_dir(data.name).exists()
            or self._legacy_path_exists(data.name)
        ):
            raise FileExistsError(data.name)
        if data.storage_path is None and self._managed_storage_path(data.name).exists():
            raise FileExistsError(data.name)
        self._write_raw(data.name, self._empty_raw(data))
        return self._metadata_from_raw(data.name, self._read_raw(data.name), path)

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

    def delete_workflow(self, name: str) -> None:
        path = self._path_for(name)
        legacy_paths = [
            candidate for candidate in self._legacy_paths_for(name) if candidate.exists()
        ]
        if path.exists() or legacy_paths:
            if legacy_paths and not path.exists():
                for legacy_path in legacy_paths:
                    legacy_path.unlink()
            else:
                shutil.rmtree(path.parent)
                for legacy_path in legacy_paths:
                    legacy_path.unlink()
        else:
            raise FileNotFoundError(name)
        managed_path = self._managed_storage_path(name)
        if managed_path.exists() and managed_path.is_relative_to(self.storage_base_dir):
            shutil.rmtree(managed_path)

    def patch_workflow(self, name: str, patch: WorkflowUpdate) -> WorkflowInfo:
        path = self._existing_path_for(name)
        raw = self._read_raw(name)
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        if patch.action == "duplicate":
            if patch.new_name is None:
                raise ValueError("new_name is required for duplicate")
            new_name = self._validate_name(patch.new_name)
            new_path = self._path_for(new_name)
            if new_path.exists() or self._legacy_path_exists(new_name):
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
            self._write_raw(new_name, duplicate)
            old_tools = self._workflow_tools_dir(name)
            new_tools = self._workflow_tools_dir(new_name)
            if old_tools.exists():
                if new_tools.exists():
                    shutil.rmtree(new_tools)
                shutil.copytree(old_tools, new_tools)
            return self._metadata_from_raw(new_name, self._read_raw(new_name), new_path)

        old_folder = self._folder_name(name)
        new_name = name
        if patch.new_id is not None:
            new_name = self._validate_name(patch.new_id)
        elif patch.new_name is not None:
            new_leaf = self._leaf_name(patch.new_name)
            target_folder = patch.folder if patch.folder is not None else old_folder
            new_name = f"{target_folder}/{new_leaf}" if target_folder else new_leaf
            new_name = self._validate_name(new_name)
        elif patch.folder is not None:
            new_leaf = self._leaf_name(name)
            new_name = f"{patch.folder}/{new_leaf}" if patch.folder else new_leaf
            new_name = self._validate_name(new_name)
        elif patch.display_name is not None:
            try:
                new_leaf = canonical_workflow_name(patch.display_name)
                new_name = f"{old_folder}/{new_leaf}" if old_folder else new_leaf
            except ValidationError:
                new_name = name
        if new_name != name and self._has_name_collision(new_name):
            raise FileExistsError(new_name)

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
        self._write_raw(new_name, raw)
        return self._metadata_from_raw(
            new_name,
            self._read_raw(new_name),
            self._path_for(new_name),
        )

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

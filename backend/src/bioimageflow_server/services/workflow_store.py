"""Filesystem-backed workflow persistence service."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import (
    ExportedWorkflow,
    LocalToolReference,
    RequiredPackage,
    WorkflowCreate,
    WorkflowExportDocument,
    WorkflowFile,
    WorkflowInfo,
    WorkflowImportResponse,
    WorkflowSaveBody,
    WorkflowUpdate,
    canonical_workflow_name,
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


class WorkflowImportParseError(ValueError):
    """Raised when an import upload is not parseable JSON."""


class WorkflowImportValidationError(ValueError):
    """Raised when an import upload is JSON but not a supported export document."""


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
    ) -> None:
        self.root_dir = root_dir
        self.tool_registry = tool_registry
        self.storage_base_dir = storage_base_dir or root_dir / "outputs"

    def _validate_name(self, name: str) -> str:
        return WorkflowCreate(name=name).name

    def _path_for(self, name: str) -> Path:
        safe_name = self._validate_name(name)
        return self.root_dir / f"{safe_name}.json"

    def _managed_storage_path(self, name: str) -> Path:
        return self.storage_base_dir / self._validate_name(name)

    def _has_name_collision(self, name: str) -> bool:
        return self._path_for(name).exists() or self._managed_storage_path(name).exists()

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
            name=name,
            display_name=str(metadata.get("display_name") or name),
            description=cast(str | None, metadata.get("description")),
            storage_path=cast(str | None, metadata.get("storage_path")),
            path=str(path),
            last_modified=last_modified,
        )

    def _read_raw(self, name: str) -> dict[str, Any]:
        path = self._path_for(name)
        if not path.exists():
            raise FileNotFoundError(name)
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
            return Path(storage_path)
        return self._managed_storage_path(name)

    def _write_raw(self, name: str, raw: dict[str, Any]) -> None:
        path = self._path_for(name)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.root_dir),
            prefix=f".{name}.",
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
        metadata = {
            "display_name": data.display_name or data.name,
            "description": data.description,
            "storage_path": data.storage_path or str(self._managed_storage_path(data.name)),
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
        path = self._path_for(name)
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

    def import_workflow(
        self,
        document: WorkflowExportDocument,
        *,
        name_override: str | None = None,
    ) -> WorkflowImportResponse:
        imported_name = self._validate_name(name_override or document.workflow.name)
        if self._has_name_collision(imported_name):
            raise FileExistsError(imported_name)

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
        for path in sorted(self.root_dir.glob("*.json")):
            if path.name.startswith("."):
                continue
            name = path.stem
            try:
                raw = self._read_raw(name)
                workflows.append(self._metadata_from_raw(name, raw, path))
            except (OSError, json.JSONDecodeError, ValidationError, ValueError):
                continue
        return workflows

    def create_workflow(self, data: WorkflowCreate) -> WorkflowInfo:
        path = self._path_for(data.name)
        if path.exists():
            raise FileExistsError(data.name)
        if data.storage_path is None and self._managed_storage_path(data.name).exists():
            raise FileExistsError(data.name)
        self._write_raw(data.name, self._empty_raw(data))
        return self._metadata_from_raw(data.name, self._read_raw(data.name), path)

    def get_workflow(self, name: str) -> WorkflowFile:
        path = self._path_for(name)
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
        path = self._path_for(name)
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
        if not path.exists():
            raise FileNotFoundError(name)
        path.unlink()
        managed_path = self._managed_storage_path(name)
        if managed_path.exists() and managed_path.is_relative_to(self.storage_base_dir):
            shutil.rmtree(managed_path)

    def patch_workflow(self, name: str, patch: WorkflowUpdate) -> WorkflowInfo:
        path = self._path_for(name)
        raw = self._read_raw(name)
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        if patch.action == "duplicate":
            if patch.new_name is None:
                raise ValueError("new_name is required for duplicate")
            new_name = self._validate_name(patch.new_name)
            new_path = self._path_for(new_name)
            if new_path.exists():
                raise FileExistsError(new_name)
            if patch.storage_path is None and self._managed_storage_path(new_name).exists():
                raise FileExistsError(new_name)
            duplicate = cast(dict[str, Any], json.loads(json.dumps(raw)))
            duplicate_metadata = duplicate.setdefault("metadata", {})
            if isinstance(duplicate_metadata, dict):
                duplicate_metadata["display_name"] = patch.display_name or new_name
                if patch.description is not None:
                    duplicate_metadata["description"] = patch.description
                duplicate_metadata["storage_path"] = patch.storage_path or str(
                    self._managed_storage_path(new_name)
                )
                self._set_workflow_storage_path(
                    duplicate,
                    duplicate_metadata["storage_path"],
                )
            self._write_raw(new_name, duplicate)
            return self._metadata_from_raw(new_name, self._read_raw(new_name), new_path)

        new_name = name
        if patch.new_name is not None:
            new_name = self._validate_name(patch.new_name)
        elif patch.display_name is not None:
            try:
                new_name = canonical_workflow_name(patch.display_name)
            except ValidationError:
                new_name = name
        if new_name != name and self._has_name_collision(new_name):
            raise FileExistsError(new_name)

        if patch.display_name is not None:
            metadata["display_name"] = patch.display_name
        if patch.description is not None:
            metadata["description"] = patch.description
        if patch.storage_path is not None:
            metadata["storage_path"] = patch.storage_path
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
            path.rename(self._path_for(new_name))
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

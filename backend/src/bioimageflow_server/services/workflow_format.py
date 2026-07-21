"""Compatibility migration and diagnostics for persisted workflow documents."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from bioimageflow_server.models.graph import GraphState, ToolNodeState
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.models.workflow import (
    WorkflowDocument,
    WorkflowFormatNotice,
    WorkspaceWorkflowMetadata,
)
from bioimageflow_server.models.workflow_draft import WorkflowDraftResponse
from bioimageflow_server.services.workflow_artifacts import artifact_hash


class LegacyWorkflowMigrationError(ValueError):
    """Raised when an old document cannot be converted without guessing."""


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _read_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("the file must contain a JSON object")
    return value


def _backup(path: Path, label: str) -> Path:
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()[:12]
    metadata_dir = (
        path.parent if path.parent.name == ".bioimageflow" else path.parent / ".bioimageflow"
    )
    backup = metadata_dir / "backups" / f"{label}.{digest}.json"
    if backup.exists():
        if backup.read_bytes() != content:
            raise OSError(f"backup collision at {backup}")
        return backup
    backup.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(backup.parent), prefix=f".{backup.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, backup)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return backup


def _legacy_tool_metadata(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    workflow = raw.get("workflow")
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise LegacyWorkflowMigrationError("legacy workflow metadata is missing its node list")
    result: dict[str, dict[str, Any]] = {}
    for item in workflow["nodes"]:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            result[item["name"]] = item
    return result


def _document_tool_metadata(document: WorkflowDocument) -> dict[str, dict[str, Any]]:
    return {
        node.id: {
            "tool_module": node.tool_module,
            "tool_class": node.tool_class,
            "tool_package": node.tool_package,
            "tool_package_version": node.tool_package_version,
            "source_module": node.source_module,
        }
        for node in document.graph.nodes
        if isinstance(node, ToolNodeState)
    }


def _legacy_config(raw: dict[str, Any], storage_path: str) -> dict[str, Any]:
    workflow = raw.get("workflow")
    config = workflow.get("config", {}) if isinstance(workflow, dict) else {}
    if not isinstance(config, dict):
        config = {}
    engine = config.get("engine", "wetlands")
    execution = config.get("execution", "parallel")
    if engine in {"parallel", "sequential"}:
        execution = engine
        engine = "wetlands"
    if engine not in {"direct", "wetlands"}:
        engine = "wetlands"
    if execution not in {"parallel", "sequential"}:
        execution = "parallel"
    return {
        "storage_path": str(config.get("storage_path") or storage_path),
        "engine": engine,
        "execution": execution,
    }


def convert_legacy_graph(
    graph: dict[str, Any],
    *,
    workflow_id: str,
    display_name: str,
    config: dict[str, Any],
    tool_metadata: dict[str, dict[str, Any]],
) -> GraphState:
    """Convert the flat graph shape persisted before recursive workflow documents."""

    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise LegacyWorkflowMigrationError("legacy graph nodes and edges must be arrays")
    if graph.get("published_inputs") or graph.get("published_outputs"):
        raise LegacyWorkflowMigrationError(
            "legacy published workflow interfaces require manual conversion"
        )

    nodes: list[dict[str, Any]] = []
    for index, node in enumerate(graph["nodes"]):
        if not isinstance(node, dict):
            raise LegacyWorkflowMigrationError(f"legacy node {index} is not an object")
        if node.get("sub_workflow") is not None or node.get("sub_workflow_readonly_reason"):
            raise LegacyWorkflowMigrationError(
                f"legacy nested workflow node {node.get('id', index)!r} requires manual conversion"
            )
        node_id = node.get("id")
        tool_name = node.get("tool_name")
        if not isinstance(node_id, str) or not isinstance(tool_name, str):
            raise LegacyWorkflowMigrationError(f"legacy node {index} is missing its identity")
        library_node = tool_metadata.get(node_id, {})
        position = node.get("position", [float(index * 280), 0.0])
        nodes.append(
            {
                "type": "tool",
                "id": node_id,
                "name": str(node.get("name") or node_id),
                "tool_name": tool_name,
                "position": position,
                "parameters": node.get("parameters") or {},
                "resources": node.get("resources") or {},
                "output_templates": node.get("output_templates") or {},
                "enabled": node.get("enabled", True),
                "collapsed": node.get("collapsed", False),
                "tool_module": library_node.get("tool_module"),
                "tool_class": library_node.get("tool_class") or tool_name,
                "tool_package": library_node.get("tool_package"),
                "tool_package_version": library_node.get("tool_package_version"),
                "source_module": library_node.get("source_module"),
            }
        )

    edges: list[dict[str, Any]] = []
    for index, edge in enumerate(graph["edges"]):
        if not isinstance(edge, dict):
            raise LegacyWorkflowMigrationError(f"legacy edge {index} is not an object")
        common = {
            "id": edge.get("id"),
            "source_node": edge.get("source_node"),
            "target_node": edge.get("target_node"),
        }
        if edge.get("type") == "column_ref":
            edges.append(
                {
                    **common,
                    "type": "column",
                    "source_output": edge.get("source_output"),
                    "target_input": edge.get("target_input"),
                }
            )
        elif edge.get("type") == "positional":
            edges.append(
                {
                    **common,
                    "type": "dataframe",
                    "target_position": edge.get("positional_index"),
                }
            )
        else:
            raise LegacyWorkflowMigrationError(
                f"legacy edge {edge.get('id', index)!r} has an unsupported type"
            )

    try:
        return GraphState.model_validate(
            {
                "schema_version": 1,
                "name": workflow_id.rsplit("/", 1)[-1],
                "display_name": display_name,
                "nodes": nodes,
                "edges": edges,
                "interface": {"inputs": [], "outputs": []},
                "config": config,
            }
        )
    except ValidationError as exc:
        raise LegacyWorkflowMigrationError(str(exc)) from exc


def _legacy_document(raw: dict[str, Any], workflow_id: str) -> WorkflowDocument:
    if raw.get("platform_document_version") is not None:
        raise LegacyWorkflowMigrationError("not a legacy workflow document")
    graph = raw.get("graph")
    metadata = raw.get("metadata")
    if not isinstance(graph, dict) or not isinstance(metadata, dict) or "workflow" not in raw:
        raise LegacyWorkflowMigrationError("the file is not a recognized legacy workflow document")
    display_name = str(metadata.get("display_name") or workflow_id.rsplit("/", 1)[-1])
    storage_path = str(metadata.get("storage_path") or "./bif_data")
    converted = convert_legacy_graph(
        graph,
        workflow_id=workflow_id,
        display_name=display_name,
        config=_legacy_config(raw, storage_path),
        tool_metadata=_legacy_tool_metadata(raw),
    )
    return WorkflowDocument(
        graph=converted,
        metadata=WorkspaceWorkflowMetadata(
            description=metadata.get("description"), storage_path=storage_path
        ),
        artifact_hash=artifact_hash(converted, []),
    )


def _migrate_draft(
    draft_path: Path,
    *,
    workflow_id: str,
    document: WorkflowDocument,
    tool_metadata: dict[str, dict[str, Any]],
) -> Path | None:
    if not draft_path.exists():
        return None
    raw = _read_object(draft_path)
    try:
        WorkflowDraftResponse.model_validate(raw)
        return None
    except ValidationError:
        pass
    graph = raw.get("graph")
    if not isinstance(graph, dict):
        raise LegacyWorkflowMigrationError("legacy draft graph is missing")
    converted = convert_legacy_graph(
        graph,
        workflow_id=workflow_id,
        display_name=document.graph.display_name,
        config=document.graph.config.model_dump(mode="json", by_alias=True, exclude_none=True),
        tool_metadata=tool_metadata,
    )
    validation = raw.get("validation")
    node_statuses = validation.get("node_statuses", {}) if isinstance(validation, dict) else {}
    migrated = {
        **raw,
        "workflow_id": workflow_id,
        "base_saved_revision": document.artifact_hash,
        "graph": converted.model_dump(mode="json", by_alias=True, exclude_none=True),
        "validation": ValidationResult(
            valid=True, node_statuses=cast(dict[str, Any], node_statuses), errors=[]
        ).model_dump(mode="json"),
    }
    normalized = WorkflowDraftResponse.model_validate(migrated).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    backup = _backup(draft_path, "draft.pre-recursive-format")
    _atomic_write_json(draft_path, normalized)
    return backup


def migrate_legacy_workflow(path: Path, workflow_id: str) -> WorkflowFormatNotice | None:
    """Migrate one recognized legacy workflow and its draft, preserving backups."""

    raw = _read_object(path)
    try:
        current_document = WorkflowDocument.model_validate(raw)
    except ValidationError:
        pass
    else:
        draft_backup = _migrate_draft(
            path.parent / ".bioimageflow" / "draft.json",
            workflow_id=workflow_id,
            document=current_document,
            tool_metadata=_document_tool_metadata(current_document),
        )
        if draft_backup is None:
            return None
        return WorkflowFormatNotice(
            status="migrated",
            workflow_id=workflow_id,
            path=str(path),
            detail="Updated a live draft saved by an earlier platform version.",
            backup_paths=[str(draft_backup)],
        )
    document = _legacy_document(raw, workflow_id)
    workflow_backup = _backup(path, "workflow.pre-recursive-format")
    draft_backup = _migrate_draft(
        path.parent / ".bioimageflow" / "draft.json",
        workflow_id=workflow_id,
        document=document,
        tool_metadata=_legacy_tool_metadata(raw),
    )
    _atomic_write_json(
        path,
        document.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    backups = [str(workflow_backup)]
    if draft_backup is not None:
        backups.append(str(draft_backup))
    return WorkflowFormatNotice(
        status="migrated",
        workflow_id=workflow_id,
        path=str(path),
        detail="Updated a workflow saved by an earlier platform version.",
        backup_paths=backups,
    )


def workflow_format_error(path: Path, workflow_id: str) -> WorkflowFormatNotice | None:
    """Return a user-facing diagnostic when one persisted document is invalid."""

    try:
        WorkflowDocument.model_validate(_read_object(path))
        return None
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return WorkflowFormatNotice(
            status="error",
            workflow_id=workflow_id,
            path=str(path),
            detail=f"This workflow is hidden because workflow.json is not valid: {exc}",
        )

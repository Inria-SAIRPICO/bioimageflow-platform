"""Canonical workflow hashing and destination-owned source storage."""

from __future__ import annotations

import hashlib
import base64
import ast
import json
import os
import tempfile
from copy import deepcopy
from uuid import uuid4
from pathlib import Path
from typing import Any

from bioimageflow_server.models.graph import GraphState, WorkflowNodeState


def _definition_without_provenance(graph: GraphState) -> dict[str, Any]:
    payload = graph.model_dump(mode="json", by_alias=True, exclude_none=True)

    def visit(item: dict[str, Any]) -> None:
        for node in item.get("nodes", []):
            if node.get("type") != "workflow":
                continue
            node.pop("source", None)
            child = node.get("workflow")
            if isinstance(child, dict):
                visit(child)

    visit(payload)
    return payload


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def artifact_hash(graph: GraphState, source_records: list[dict[str, Any]]) -> str:
    """Hash the editable definition and exactly its runtime source bundle."""

    records = sorted(source_records, key=lambda item: str(item.get("id", "")))
    material = {
        "graph": _definition_without_provenance(graph),
        "custom_sources": records,
    }
    return f"sha256:{hashlib.sha256(canonical_json_bytes(material)).hexdigest()}"


def referenced_source_ids(graph: GraphState) -> set[str]:
    result: set[str] = set()
    for node in graph.nodes:
        if isinstance(node, WorkflowNodeState):
            result.update(referenced_source_ids(node.workflow))
        elif node.source_module:
            result.add(node.source_module)
    return result


def fork_workflow_sources(
    graph: GraphState, records: list[dict[str, Any]]
) -> tuple[GraphState, list[dict[str, Any]]]:
    """Copy source identities when bringing another workflow into this owner."""
    identities = {record["id"]: f"source_{uuid4().hex}" for record in records}
    graph = graph.model_copy(deep=True)

    def visit(current: GraphState) -> None:
        for node in current.nodes:
            if isinstance(node, WorkflowNodeState):
                visit(node.workflow)
            elif node.source_module in identities:
                node.source_module = identities[node.source_module]

    visit(graph)
    return graph, [{**record, "id": identities[record["id"]]} for record in records]


def capture_library_sources(
    library_graph: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    """Give each execution/export snapshot its own content-derived module IDs.

    Working source IDs are stable while files are edited. Library module names
    must change with their bytes so Python package imports cannot reuse old code.
    """
    if not records:
        return library_graph
    graph = deepcopy(library_graph)
    captured = []
    identities = {}
    for record in records:
        identity = "m_" + hashlib.sha256(canonical_json_bytes(record)).hexdigest()
        identities[record["id"]] = identity
        captured.append({**record, "id": identity})

    def visit(current: dict[str, Any]) -> None:
        for node in current["nodes"]:
            if node["type"] == "workflow":
                visit(node["workflow"])
            elif node.get("source_module") in identities:
                node["source_module"] = identities[node["source_module"]]

    visit(graph)
    return {"archive_version": 1, "workflow": graph, "custom_sources": captured}


def resolve_local_source(workflow_dir: Path, class_name: str, registry: Any = None) -> Path | None:
    """Resolve a local class by its definition, never by a guessed filename."""
    if registry is not None:
        registered = registry.resolve_tool_source(class_name)
        root = (workflow_dir / "tools").resolve()
        if registered is not None and registered.resolve().is_relative_to(root):
            return OwnedWorkflowSources._safe_file(
                root, registered.resolve().relative_to(root).as_posix()
            )
    matches = []
    for path in sorted((workflow_dir / "tools").glob("*.py")):
        tree = ast.parse(path.read_bytes(), filename=str(path))
        if any(isinstance(node, ast.ClassDef) and node.name == class_name for node in tree.body):
            matches.append(OwnedWorkflowSources._safe_file(workflow_dir / "tools", path.name))
    if len(matches) > 1:
        raise ValueError(
            f"Several workflow files define {class_name}; an explicit source binding is required"
        )
    return matches[0] if matches else None


def capture_working_graph(
    graph: GraphState, workflow_dir: Path, registry: Any
) -> tuple[GraphState, list[dict[str, Any]]]:
    """Capture editable bytes once before compilation, independent of watcher timing."""
    working = graph.model_copy(deep=True)
    records = OwnedWorkflowSources(workflow_dir).collect_for_graph(working)
    captured = {record["id"] for record in records}

    def visit(current: GraphState) -> None:
        for node in current.nodes:
            if isinstance(node, WorkflowNodeState):
                visit(node.workflow)
                continue
            if node.source_module:
                continue
            metadata = registry.get_tool(node.tool_name)
            if metadata is not None and metadata.source_kind != "custom":
                continue
            path = resolve_local_source(workflow_dir, node.tool_class or node.tool_name, registry)
            if path is None:
                continue
            source = path.read_text(encoding="utf-8")
            source_id = "local_" + hashlib.sha256(path.name.encode()).hexdigest()
            node.source_module = source_id
            node.tool_class = node.tool_class or node.tool_name
            node.tool_module = path.stem
            node.tool_package = None
            node.tool_package_version = None
            if source_id not in captured:
                records.append(
                    {
                        "id": source_id,
                        "module": path.stem,
                        "filename": path.name,
                        "source": source,
                        "source_hash": hashlib.sha256(source.encode()).hexdigest(),
                    }
                )
                captured.add(source_id)

    visit(working)
    return working, records


def rewrite_workspace_source_ids(graph: GraphState, mapping: dict[str, str]) -> GraphState:
    """Return a graph whose optional workspace provenance follows identity moves."""

    nodes = []
    for node in graph.nodes:
        if not isinstance(node, WorkflowNodeState):
            nodes.append(node)
            continue
        source = node.source
        if source is not None and source.workflow_id in mapping:
            source = source.model_copy(update={"workflow_id": mapping[source.workflow_id]})
        nodes.append(
            node.model_copy(
                update={
                    "workflow": rewrite_workspace_source_ids(node.workflow, mapping),
                    "source": source,
                }
            )
        )
    return graph.model_copy(update={"nodes": nodes})


class OwnedWorkflowSources:
    """Editable source directories owned by a workflow.

    The manifest records identity and module layout only. Source bytes always
    come from ordinary files; archive records are captured at the API boundary.
    """

    def __init__(self, workflow_dir: Path) -> None:
        self.root = workflow_dir / "tools"

    def _path(self, source_id: str) -> Path:
        if not source_id or any(part in source_id for part in ("/", "\\", "..")):
            raise ValueError(f"Invalid custom source ID: {source_id!r}")
        return self._safe_file(self.root, f"{source_id}/module.json")

    def source_path(self, source_id: str, module: str | None = None) -> Path:
        manifest_path = self._path(source_id)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if "root_package" in manifest:
            name = module or manifest["module"]
            root_package = manifest["root_package"]
            if not (name == root_package or name.startswith(root_package + ".")):
                name = root_package + "." + name
            relative = name.replace(".", "/") + ".py"
            path = self._safe_file(manifest_path.parent, relative)
            if not path.exists():
                path = self._safe_file(
                    manifest_path.parent, name.replace(".", "/") + "/__init__.py"
                )
        else:
            path = self._safe_file(manifest_path.parent, manifest["filename"])
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    @staticmethod
    def _safe_file(root: Path, relative: str) -> Path:
        path = Path(relative)
        if (
            path.is_absolute()
            or not path.parts
            or any(p in ("..", ".") for p in path.parts)
            or "\\" in relative
        ):
            raise ValueError(f"Invalid workflow source path: {relative!r}")
        target = root / path
        candidate = target
        while True:
            if candidate.is_symlink():
                raise ValueError(f"Symlinks are not allowed in workflow sources: {candidate}")
            if candidate == root:
                break
            candidate = candidate.parent
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Workflow source escapes its directory: {relative!r}")
        return target

    def read(self, source_id: str) -> dict[str, Any]:
        path = self._path(source_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("id") != source_id:
            raise ValueError(f"Invalid owned source record: {source_id}")
        if "root_package" in data:
            files = []
            digest = hashlib.sha256()
            package = self._safe_file(path.parent, data["root_package"])
            for item in sorted(package.rglob("*")):
                if "__pycache__" in item.parts or item.suffix in (".pyc", ".pyo"):
                    continue
                if item.is_symlink():
                    raise ValueError(f"Symlinks are not allowed in workflow sources: {item}")
                if not item.is_file():
                    continue
                relative = item.relative_to(path.parent).as_posix()
                content = self._safe_file(path.parent, relative).read_bytes()
                file_hash = hashlib.sha256(content).hexdigest()
                digest.update(relative.encode() + b"\0" + file_hash.encode() + b"\0")
                files.append(
                    {
                        "path": relative,
                        "encoding": "base64",
                        "content": base64.b64encode(content).decode(),
                        "source_hash": file_hash,
                    }
                )
            data.update(files=files, source_hash=digest.hexdigest())
        else:
            source = self.source_path(source_id).read_text(encoding="utf-8")
            data.update(source=source, source_hash=hashlib.sha256(source.encode()).hexdigest())
        return data

    def read_many(self, source_ids: set[str] | list[str]) -> list[dict[str, Any]]:
        return [self.read(source_id) for source_id in sorted(source_ids)]

    def stage(self, records: list[dict[str, Any]]) -> list[tuple[Path, Path]]:
        """Write verified temporary records without publishing them."""

        contents: list[tuple[Path, bytes]] = []
        for record in records:
            source_id = record.get("id")
            if not isinstance(source_id, str):
                raise ValueError("Custom source record has no string ID")
            final_path = self._path(source_id)
            if final_path.exists():
                if self.read(source_id) != record:
                    raise ValueError(f"Custom source ID collision: {source_id}")
                continue
            manifest = {
                key: value
                for key, value in record.items()
                if key not in ("source", "files", "source_hash")
            }
            contents.append((final_path, canonical_json_bytes(manifest) + b"\n"))
            if "files" in record:
                package_root = self._safe_file(final_path.parent, record["root_package"])
                for file in record["files"]:
                    content = base64.b64decode(file["content"], validate=True)
                    if hashlib.sha256(content).hexdigest() != file["source_hash"]:
                        raise ValueError("Workflow source file hash mismatch")
                    destination = self._safe_file(final_path.parent, file["path"])
                    if not destination.is_relative_to(package_root):
                        raise ValueError("Workflow source file is outside its package")
                    contents.append((destination, content))
            else:
                content = record["source"].encode("utf-8")
                if hashlib.sha256(content).hexdigest() != record["source_hash"]:
                    raise ValueError("Workflow source hash mismatch")
                destination = self._safe_file(final_path.parent, record["filename"])
                if destination.suffix != ".py":
                    raise ValueError("Workflow source must be a Python file")
                contents.append((destination, content))
        destinations = [destination for destination, _ in contents]
        if len(set(destinations)) != len(destinations):
            raise ValueError("Duplicate workflow source paths")
        staged: list[tuple[Path, Path]] = []
        try:
            for destination, content in contents:
                destination.parent.mkdir(parents=True, exist_ok=True)
                fd, raw_path = tempfile.mkstemp(
                    dir=destination.parent, prefix=".source.", suffix=".tmp"
                )
                tmp_path = Path(raw_path)
                try:
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                except Exception:
                    tmp_path.unlink(missing_ok=True)
                    raise
                staged.append((tmp_path, destination))
        except Exception:
            self.discard(staged)
            raise
        return staged

    @staticmethod
    def publish(staged: list[tuple[Path, Path]]) -> None:
        for temporary, final in staged:
            os.replace(temporary, final)

    @staticmethod
    def discard(staged: list[tuple[Path, Path]]) -> None:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)

    def collect_for_graph(self, graph: GraphState) -> list[dict[str, Any]]:
        return self.read_many(referenced_source_ids(graph))

"""Canonical workflow hashing and destination-owned source storage."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
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


def rewrite_workspace_source_ids(
    graph: GraphState, mapping: dict[str, str]
) -> GraphState:
    """Return a graph whose optional workspace provenance follows identity moves."""

    nodes = []
    for node in graph.nodes:
        if not isinstance(node, WorkflowNodeState):
            nodes.append(node)
            continue
        source = node.source
        if source is not None and source.workflow_id in mapping:
            source = source.model_copy(
                update={"workflow_id": mapping[source.workflow_id]}
            )
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
    """Content-addressed runtime source records owned by one root workflow."""

    def __init__(self, workflow_dir: Path) -> None:
        self.root = workflow_dir / ".bioimageflow" / "dependencies"

    def _path(self, source_id: str) -> Path:
        if not source_id or any(part in source_id for part in ("/", "\\", "..")):
            raise ValueError(f"Invalid custom source ID: {source_id!r}")
        return self.root / source_id / "source.json"

    def read(self, source_id: str) -> dict[str, Any]:
        path = self._path(source_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("id") != source_id:
            raise ValueError(f"Invalid owned source record: {source_id}")
        return data

    def read_many(self, source_ids: set[str] | list[str]) -> list[dict[str, Any]]:
        return [self.read(source_id) for source_id in sorted(source_ids)]

    def stage(self, records: list[dict[str, Any]]) -> list[tuple[Path, Path]]:
        """Write verified temporary records without publishing them."""

        staged: list[tuple[Path, Path]] = []
        self.root.mkdir(parents=True, exist_ok=True)
        for record in records:
            source_id = record.get("id")
            if not isinstance(source_id, str):
                raise ValueError("Custom source record has no string ID")
            final_path = self._path(source_id)
            if final_path.exists():
                if self.read(source_id) != record:
                    raise ValueError(f"Custom source ID collision: {source_id}")
                continue
            final_path.parent.mkdir(parents=True, exist_ok=True)
            fd, raw_path = tempfile.mkstemp(
                dir=str(final_path.parent), prefix=".source.", suffix=".tmp"
            )
            tmp_path = Path(raw_path)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(canonical_json_bytes(record))
                    handle.write(b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
            staged.append((tmp_path, final_path))
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

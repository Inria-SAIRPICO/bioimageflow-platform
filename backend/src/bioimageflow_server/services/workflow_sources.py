"""Explicit source refresh and trusted Python materialization transactions."""

from __future__ import annotations

import hashlib
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from bioimageflow import Workflow

from bioimageflow_server.models.graph import (
    ColumnEdge,
    GraphState,
    WorkflowNodeState,
    WorkspaceWorkflowSource,
)
from bioimageflow_server.models.workflow import (
    PythonAuthoringProvenance,
    WorkflowDocument,
)
from bioimageflow_server.models.workflow_sources import (
    SourceDestructiveEffect,
    WorkflowSourceApplyRequest,
    WorkflowSourceApplyResponse,
    WorkflowSourcePreview,
)
from bioimageflow_server.services.graph_translator import lib_dict_to_graph_state
from bioimageflow_server.services.workflow_artifacts import (
    OwnedWorkflowSources,
    artifact_hash,
    canonical_json_bytes,
    referenced_source_ids,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService


class WorkflowSourceConflict(ValueError):
    pass


@dataclass(frozen=True)
class _PreparedSourceOperation:
    preview: WorkflowSourcePreview
    source_records: tuple[dict[str, Any], ...]
    old_source_hash: str | None
    python_manifest: tuple[tuple[str, bytes], ...] = ()


class WorkflowSourceService:
    """Keep preview/apply source replacements immutable and revision checked."""

    def __init__(
        self,
        store_provider: Callable[[], WorkflowStoreService],
        *,
        deployment_mode_provider: Callable[[], str] | None = None,
        unsafe_webapp_features_provider: Callable[[], bool] | None = None,
        has_open_nested_editor: Callable[[str, list[str]], bool] | None = None,
    ) -> None:
        self._store_provider = store_provider
        self._deployment_mode_provider = deployment_mode_provider or (lambda: "desktop")
        self._unsafe_webapp_features_provider = (
            unsafe_webapp_features_provider or (lambda: False)
        )
        self._has_open_nested_editor = has_open_nested_editor or (
            lambda _workflow_id, _path: False
        )
        self._prepared: dict[UUID, _PreparedSourceOperation] = {}
        self._lock = threading.RLock()

    def preview_source_update(
        self,
        workflow_id: str,
        workflow_path: list[str],
        *,
        expected_artifact_hash: str,
    ) -> WorkflowSourcePreview:
        store = self._store_provider()
        parent = store.get_workflow(workflow_id)
        if parent.artifact_hash != expected_artifact_hash:
            raise WorkflowSourceConflict("Parent workflow artifact changed")
        target = _workflow_node_at(parent.graph, workflow_path)
        if target.source is None:
            raise ValueError("Workflow node has no workspace source provenance")
        source = store.get_workflow(target.source.workflow_id)
        source_records = OwnedWorkflowSources(
            store.workflow_dir(target.source.workflow_id)
        ).collect_for_graph(source.graph)
        effects = _destructive_effects(parent.graph, workflow_path, source.graph)
        current_ids = referenced_source_ids(parent.graph)
        replacement_ids = referenced_source_ids(source.graph)
        preview = WorkflowSourcePreview(
            token=uuid4(),
            operation="source_update",
            workflow_id=workflow_id,
            workflow_path=workflow_path,
            parent_artifact_hash=parent.artifact_hash,
            source_artifact_hash=source.artifact_hash,
            destructive_effects=effects,
            custom_source_ids_added=sorted(replacement_ids - current_ids),
            custom_source_ids_removed=sorted(current_ids - replacement_ids),
            replacement=source.graph,
        )
        prepared = _PreparedSourceOperation(
            preview=preview,
            source_records=tuple(source_records),
            old_source_hash=target.source.artifact_hash,
        )
        with self._lock:
            self._prepared[preview.token] = prepared
        return preview

    def preview_python_rebuild(
        self,
        workflow_id: str,
        *,
        expected_artifact_hash: str,
    ) -> WorkflowSourcePreview:
        self._require_trusted_mode()
        store = self._store_provider()
        current = store.get_workflow(workflow_id)
        if current.artifact_hash != expected_artifact_hash:
            raise WorkflowSourceConflict("Workflow artifact changed")
        root = store.workflow_dir(workflow_id)
        manifest = _capture_python_manifest(root)
        graph, sources = _materialize_python_manifest(manifest)
        preview = WorkflowSourcePreview(
            token=uuid4(),
            operation="python_rebuild",
            workflow_id=workflow_id,
            parent_artifact_hash=current.artifact_hash,
            source_artifact_hash=_manifest_hash(manifest),
            destructive_effects=_root_replacement_effects(current.graph, graph),
            custom_source_ids_added=sorted(
                referenced_source_ids(graph) - referenced_source_ids(current.graph)
            ),
            custom_source_ids_removed=sorted(
                referenced_source_ids(current.graph) - referenced_source_ids(graph)
            ),
            replacement=graph,
        )
        with self._lock:
            self._prepared[preview.token] = _PreparedSourceOperation(
                preview=preview,
                source_records=tuple(sources),
                old_source_hash=None,
                python_manifest=tuple(manifest),
            )
        return preview

    def apply(self, request: WorkflowSourceApplyRequest) -> WorkflowSourceApplyResponse:
        with self._lock:
            prepared = self._prepared.get(request.token)
        if prepared is None:
            raise WorkflowSourceConflict("Unknown or expired source preview token")
        expected = [item.model_dump(mode="json") for item in prepared.preview.destructive_effects]
        confirmed = [item.model_dump(mode="json") for item in request.confirm_effects]
        if expected != confirmed:
            raise WorkflowSourceConflict("Destructive effects were not confirmed exactly")
        if prepared.preview.operation == "python_rebuild":
            result = self._apply_python(prepared)
        else:
            result = self._apply_source(prepared)
        with self._lock:
            self._prepared.pop(request.token, None)
        return result

    def _apply_source(
        self, prepared: _PreparedSourceOperation
    ) -> WorkflowSourceApplyResponse:
        preview = prepared.preview
        store = self._store_provider()
        if self._has_open_nested_editor(preview.workflow_id, preview.workflow_path):
            raise WorkflowSourceConflict("A target or descendant workflow editor is open")
        with store.workflow_mutation(preview.workflow_id):
            parent = store.get_workflow(preview.workflow_id)
            if parent.artifact_hash != preview.parent_artifact_hash:
                raise WorkflowSourceConflict("Parent workflow artifact changed")
            target = _workflow_node_at(parent.graph, preview.workflow_path)
            if target.source is None or target.source.artifact_hash != prepared.old_source_hash:
                raise WorkflowSourceConflict("Embedded source provenance changed")
            source = store.get_workflow(target.source.workflow_id)
            if source.artifact_hash != preview.source_artifact_hash:
                raise WorkflowSourceConflict("Saved source artifact changed")
            graph = _replace_workflow_node(
                parent.graph,
                preview.workflow_path,
                preview.replacement,
                WorkspaceWorkflowSource(
                    kind="workspace",
                    workflow_id=target.source.workflow_id,
                    artifact_hash=preview.source_artifact_hash,
                ),
            )
            return self._commit_graph_and_sources(
                store,
                preview.workflow_id,
                graph,
                list(prepared.source_records),
                authoring_source=parent.authoring_source,
            )

    def _apply_python(
        self, prepared: _PreparedSourceOperation
    ) -> WorkflowSourceApplyResponse:
        self._require_trusted_mode()
        preview = prepared.preview
        store = self._store_provider()
        if self._has_open_nested_editor(preview.workflow_id, []):
            raise WorkflowSourceConflict("A nested workflow editor is open")
        live_manifest = _capture_python_manifest(store.workflow_dir(preview.workflow_id))
        if _manifest_hash(live_manifest) != preview.source_artifact_hash:
            raise WorkflowSourceConflict("Python authoring source changed after preview")
        with store.workflow_mutation(preview.workflow_id):
            current = store.get_workflow(preview.workflow_id)
            if current.artifact_hash != preview.parent_artifact_hash:
                raise WorkflowSourceConflict("Workflow artifact changed")
            provenance = PythonAuthoringProvenance(
                source_id="workflow.py",
                source_hash=preview.source_artifact_hash,
            )
            return self._commit_graph_and_sources(
                store,
                preview.workflow_id,
                preview.replacement,
                list(prepared.source_records),
                authoring_source=provenance,
            )

    def _commit_graph_and_sources(
        self,
        store: WorkflowStoreService,
        workflow_id: str,
        graph: GraphState,
        source_records: list[dict[str, Any]],
        *,
        authoring_source: PythonAuthoringProvenance | None,
    ) -> WorkflowSourceApplyResponse:
        store.validate_containment(workflow_id, graph)
        owned = OwnedWorkflowSources(store.workflow_dir(workflow_id))
        staged = owned.stage(source_records)
        published: list[Path] = []
        try:
            for temporary, final in staged:
                final.parent.mkdir(parents=True, exist_ok=True)
                temporary.replace(final)
                published.append(final)
            all_records = owned.collect_for_graph(graph)
            current = WorkflowDocument.model_validate(store._read_raw(workflow_id))
            document = current.model_copy(
                update={
                    "graph": graph,
                    "authoring_source": authoring_source,
                    "owned_source_ids": sorted(referenced_source_ids(graph)),
                    "artifact_hash": artifact_hash(graph, all_records),
                }
            )
            store._write_raw(
                workflow_id,
                document.model_dump(mode="json", by_alias=True, exclude_none=True),
            )
        except Exception:
            OwnedWorkflowSources.discard(staged)
            for path in published:
                path.unlink(missing_ok=True)
            raise
        return WorkflowSourceApplyResponse(
            graph=graph,
            artifact_hash=document.artifact_hash,
        )

    def _require_trusted_mode(self) -> None:
        if (
            self._deployment_mode_provider() == "webapp"
            and not self._unsafe_webapp_features_provider()
        ):
            raise PermissionError("Python workflow materialization is disabled in webapp mode")


def _workflow_node_at(graph: GraphState, path: list[str]) -> WorkflowNodeState:
    current = graph
    node: WorkflowNodeState | None = None
    for node_id in path:
        candidate = next((item for item in current.nodes if item.id == node_id), None)
        if not isinstance(candidate, WorkflowNodeState):
            raise ValueError(f"Workflow node path not found: {'/'.join(path)}")
        node = candidate
        current = node.workflow
    if node is None:
        raise ValueError("Workflow node path must not be empty")
    return node


def _destructive_effects(
    root: GraphState, path: list[str], replacement: GraphState
) -> list[SourceDestructiveEffect]:
    target = _workflow_node_at(root, path)
    old_inputs = {item.id: item for item in target.workflow.interface.inputs}
    new_inputs = {item.id: item for item in replacement.interface.inputs}
    old_outputs = {item.id: item for item in target.workflow.interface.outputs}
    new_outputs = {item.id: item for item in replacement.interface.outputs}
    parent = root
    for node_id in path[:-1]:
        parent = _workflow_node_at(parent, [node_id]).workflow
    node_id = path[-1]
    effects: list[SourceDestructiveEffect] = []
    for port_id, old in old_inputs.items():
        new = new_inputs.get(port_id)
        kind: Literal["removed_input", "changed_input"] | None = None
        if new is None:
            kind = "removed_input"
        elif old.kind != new.kind or old.schema_ != new.schema_:
            kind = "changed_input"
        if kind:
            effects.append(
                SourceDestructiveEffect(
                    kind=kind,
                    port_id=port_id,
                    affected_edge_ids=[
                        edge.id
                        for edge in parent.edges
                        if edge.target_node == node_id and edge.target_input == port_id
                    ],
                    affected_binding=port_id in target.bindings,
                )
            )
    for port_id, old in old_outputs.items():
        new = new_outputs.get(port_id)
        kind: Literal["removed_output", "changed_output"] | None = None
        if new is None:
            kind = "removed_output"
        elif old.schema_ != new.schema_:
            kind = "changed_output"
        if kind:
            effects.append(
                SourceDestructiveEffect(
                    kind=kind,
                    port_id=port_id,
                    affected_edge_ids=[
                        edge.id
                        for edge in parent.edges
                        if isinstance(edge, ColumnEdge)
                        and edge.source_node == node_id
                        and edge.source_output == port_id
                    ],
                )
            )
    return effects


def _root_replacement_effects(
    current: GraphState, replacement: GraphState
) -> list[SourceDestructiveEffect]:
    # Root replacement has no parent edges/bindings, but the same stable-port
    # compatibility summary tells the user which public contract changed.
    wrapper = WorkflowNodeState(
        type="workflow",
        id="root",
        name="root",
        workflow=current,
        bindings={},
        position=(0, 0),
    )
    root = GraphState(
        schema_version=1,
        name="preview",
        display_name="Preview",
        nodes=[wrapper],
        edges=[],
        interface={"inputs": [], "outputs": []},
        config={},
    )
    return _destructive_effects(root, ["root"], replacement)


def _replace_workflow_node(
    graph: GraphState,
    path: list[str],
    replacement: GraphState,
    source: WorkspaceWorkflowSource,
) -> GraphState:
    node_id = path[0]
    node = _workflow_node_at(graph, [node_id])
    if len(path) > 1:
        child = _replace_workflow_node(node.workflow, path[1:], replacement, source)
        updated = node.model_copy(update={"workflow": child})
    else:
        input_ids = {item.id for item in replacement.interface.inputs}
        output_ids = {item.id for item in replacement.interface.outputs}
        updated = node.model_copy(
            update={
                "workflow": replacement,
                "source": source,
                "bindings": {
                    key: value for key, value in node.bindings.items() if key in input_ids
                },
            }
        )
        edges = [
            edge
            for edge in graph.edges
            if not (
                edge.target_node == node_id
                and edge.target_input is not None
                and edge.target_input not in input_ids
            )
            and not (
                isinstance(edge, ColumnEdge)
                and edge.source_node == node_id
                and edge.source_output not in output_ids
            )
        ]
        return graph.model_copy(
            update={
                "nodes": [updated if item.id == node_id else item for item in graph.nodes],
                "edges": edges,
            }
        )
    return graph.model_copy(
        update={"nodes": [updated if item.id == node_id else item for item in graph.nodes]}
    )


def _capture_python_manifest(root: Path) -> list[tuple[str, bytes]]:
    entry = root / "workflow.py"
    if not entry.exists() or entry.is_symlink() or not entry.is_file():
        raise FileNotFoundError("Trusted authoring source workflow.py was not found")
    resolved_root = root.resolve()
    result: list[tuple[str, bytes]] = []
    for path in sorted(root.rglob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Python authoring source cannot use symlinks: {path}")
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Python authoring source escapes workflow root: {path}") from exc
        if any(part in {"__pycache__", ".bioimageflow"} for part in path.parts):
            continue
        result.append((relative, path.read_bytes()))
    if "workflow.py" not in {name for name, _ in result}:
        raise FileNotFoundError("Trusted authoring source workflow.py was not found")
    return result


def _manifest_hash(manifest: list[tuple[str, bytes]]) -> str:
    records = [
        {"path": path, "sha256": hashlib.sha256(content).hexdigest()}
        for path, content in manifest
    ]
    return f"sha256:{hashlib.sha256(canonical_json_bytes(records)).hexdigest()}"


def _materialize_python_manifest(
    manifest: list[tuple[str, bytes]],
) -> tuple[GraphState, list[dict[str, Any]]]:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        for relative, content in manifest:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        workflow = Workflow.from_python(root / "workflow.py")
        exported = workflow.to_dict(include_custom_tools=True)
    graph = lib_dict_to_graph_state(exported)
    sources = (
        exported.get("custom_sources", [])
        if set(exported) == {"archive_version", "workflow", "custom_sources"}
        else []
    )
    if not isinstance(sources, list):
        raise ValueError("Python workflow produced malformed custom source records")
    return graph, sources

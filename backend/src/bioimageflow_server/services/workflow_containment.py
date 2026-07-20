"""Workspace-provenance containment validation for recursive snapshots."""

from __future__ import annotations

from collections.abc import Callable

from bioimageflow_server.models.graph import GraphState, WorkflowNodeState


class WorkflowContainmentError(ValueError):
    def __init__(self, path: list[str]) -> None:
        self.path = path
        super().__init__(
            "Workflow source containment cycle: " + " -> ".join(path)
        )


def validate_workflow_containment(
    destination_workflow_id: str,
    graph: GraphState,
    *,
    resolve_saved_graph: Callable[[str], GraphState] | None = None,
) -> None:
    """Reject direct or transitive source identity cycles with a complete path."""

    visited_sources: set[str] = set()

    def visit_graph(current: GraphState, path: list[str]) -> None:
        for node in current.nodes:
            if not isinstance(node, WorkflowNodeState):
                continue
            node_path = [*path, node.id]
            visit_graph(node.workflow, node_path)
            if node.source is None:
                continue
            source_id = node.source.workflow_id
            source_path = [*node_path, f"source:{source_id}"]
            if source_id == destination_workflow_id:
                raise WorkflowContainmentError(source_path)
            if resolve_saved_graph is None or source_id in visited_sources:
                continue
            visited_sources.add(source_id)
            try:
                source_graph = resolve_saved_graph(source_id)
            except FileNotFoundError:
                # Embedded content remains authoritative when the source was
                # removed; a missing provenance target cannot create a cycle.
                continue
            visit_graph(source_graph, source_path)

    visit_graph(graph, [destination_workflow_id])

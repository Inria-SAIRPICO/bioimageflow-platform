"""Project workflow-node badges from their executable descendants."""

from collections.abc import Collection

from bioimageflow_server.models.graph import GraphState, WorkflowNodeState
from bioimageflow_server.models.validation import NodeStatus


def aggregate_workflow_statuses(
    graph: GraphState,
    node_statuses: dict[str, NodeStatus],
    *,
    selected_leaf_ids: Collection[str] | None = None,
) -> dict[str, NodeStatus]:
    """Return statuses for workflow boundaries with enabled selected tool descendants."""

    selected = set(selected_leaf_ids) if selected_leaf_ids is not None else None
    aggregates: dict[str, NodeStatus] = {}

    def visit(current: GraphState, prefix: str = "") -> list[str]:
        leaves: list[str] = []
        for node in current.nodes:
            node_id = f"{prefix}/{node.id}" if prefix else node.id
            if not node.enabled:
                continue
            if isinstance(node, WorkflowNodeState):
                descendants = visit(node.workflow, node_id)
                if descendants:
                    children = [node_statuses.get(child_id) for child_id in descendants]
                    failed = next(
                        (
                            child
                            for child in children
                            if child is not None and child.status == "failed"
                        ),
                        None,
                    )
                    if failed is not None:
                        status = "failed"
                    elif any(child is not None and child.status == "running" for child in children):
                        status = "running"
                    elif any(child is not None and child.status == "out_of_date" for child in children):
                        status = "out_of_date"
                    elif all(child is not None and child.status == "executed" for child in children):
                        status = "executed"
                    else:
                        status = "unexecuted"
                    aggregates[node_id] = NodeStatus(
                        node_id=node_id,
                        status=status,
                        cached=status == "executed"
                        and all(child.cached for child in children if child is not None),
                        error=(
                            f"Node '{failed.node_id}' failed: {failed.error or 'Execution failed'}"
                            if failed is not None
                            else None
                        ),
                    )
                    leaves.extend(descendants)
            elif selected is None or node_id in selected:
                leaves.append(node_id)
        return leaves

    visit(graph)
    return aggregates

"""Check worker overrides against the actual public materialized node."""

from __future__ import annotations

from typing import Any

from bioimageflow_server.models.validation import GraphValidationError


def materialized_resource_errors(
    workflow: Any, payload: dict[str, Any], *, scope: tuple[str, ...] = (),
) -> list[GraphValidationError]:
    """Refuse overrides ignored by the library's DataFrame materializer.

    Processing declarations/floors are already checked during canonical
    construction. The public setter also owns DataFrame applicability, so
    callers do not reproduce that rule using a catalog class.
    """
    from bioimageflow import NodeResourceOverrides
    from bioimageflow.dataframe_tool import DataFrameTool

    graph = payload.get("workflow", payload) if "archive_version" in payload else payload
    errors: list[GraphValidationError] = []
    for item in graph.get("nodes", []):
        name = item["name"]
        node = workflow.nodes.get(name)
        if node is None:
            continue
        path = (*scope, name)
        if item.get("type") == "workflow":
            errors.extend(materialized_resource_errors(node.workflow, item["workflow"], scope=path))
        elif "resource_overrides" in item and isinstance(node.tool, DataFrameTool):
            try:
                node.set_resource_overrides(NodeResourceOverrides.from_dict(item["resource_overrides"]))
            except (TypeError, ValueError) as exc:
                errors.append(GraphValidationError(
                    type="parameter_invalid", node="/".join(path), field="resources", detail=str(exc),
                ))
    return errors

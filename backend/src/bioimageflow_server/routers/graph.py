"""Graph validation router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import (
    GraphValidationError,
    NodeStatus,
    ValidationResult,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

router = APIRouter(prefix="/graph", tags=["graph"])


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


@router.put("")
async def validate_graph(
    graph: GraphState,
    registry: ToolRegistryService = Depends(get_tool_registry),
) -> ValidationResult:
    errors: list[GraphValidationError] = []
    node_statuses: dict[str, NodeStatus] = {}

    for node in graph.nodes:
        tool = registry.get_tool(node.tool_name)
        if tool is None:
            errors.append(
                GraphValidationError(
                    type="missing_tool",
                    detail=f"Tool '{node.tool_name}' not found in registry",
                    node=node.id,
                )
            )
            continue
        node_statuses[node.id] = NodeStatus(
            node_id=node.id,
            status="unexecuted",
            cached=False,
        )

    return ValidationResult(
        valid=len(errors) == 0,
        node_statuses=node_statuses,
        errors=errors,
    )

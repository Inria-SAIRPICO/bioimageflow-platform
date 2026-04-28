"""Validation models: node statuses, graph errors, and validation results."""

from typing import Any, Literal

from pydantic import BaseModel


class NodeStatus(BaseModel):
    """Status of a single node after validation or execution."""

    node_id: str
    status: Literal[
        "unexecuted",
        "executed",
        "out_of_date",
        "disabled",
        "running",
        "failed",
    ]
    cached: bool
    error: str | None = None
    traceback: str | None = None


class GraphValidationError(BaseModel):
    """A single validation error detected in the graph."""

    type: Literal[
        "cycle_detected",
        "type_incompatible",
        "parameter_invalid",
        "missing_tool",
        "missing_connection",
        "missing_package",
        "invalid_node_id",
        "invalid_edge_id",
        "source_tool_upstream",
    ]
    detail: str
    node: str | None = None
    edge_id: str | None = None
    field: str | None = None


class ValidationResult(BaseModel):
    """Result of validating a graph."""

    valid: bool
    node_statuses: dict[str, NodeStatus] = {}
    errors: list[GraphValidationError] = []


class ParameterPatchRequest(BaseModel):
    """Body of PATCH /graph/nodes/{id}/parameters — constants only."""

    parameters: dict[str, Any]

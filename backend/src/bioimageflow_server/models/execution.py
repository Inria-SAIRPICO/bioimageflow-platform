"""Execution models: requests, progress, results, and status."""

from typing import Any, Literal

from pydantic import BaseModel

from bioimageflow_server.models.validation import NodeStatus


class ExecutionRequest(BaseModel):
    """Request to execute a graph (or a subset of its nodes)."""

    graph: dict[str, Any]
    nodes: list[str] | None = None
    workflow_name: str | None = None


class ProgressInfo(BaseModel):
    """Progress information for a running node."""

    node_id: str
    row: int
    total_rows: int


class ExecutionResult(BaseModel):
    """Result of a graph execution."""

    success: bool
    errors: list[dict[str, Any]] = []
    node_statuses: dict[str, NodeStatus] = {}


class ExecutionStatus(BaseModel):
    """Current execution status of the engine."""

    state: Literal["running", "idle"]
    last_result: ExecutionResult | None = None
    progress: ProgressInfo | None = None

"""Execution models: requests, progress, results, and status."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from bioimageflow_server.models.validation import NodeStatus
from bioimageflow_server.models.workflow import validate_workflow_id


class ExecutionRequest(BaseModel):
    """Request to execute a graph (or a subset of its nodes)."""

    graph: dict[str, Any]
    nodes: list[str] | None = None
    workflow_name: str = Field(min_length=1)

    @field_validator("workflow_name")
    @classmethod
    def validate_workflow_name(cls, value: str) -> str:
        return validate_workflow_id(value)


class ProgressInfo(BaseModel):
    """Progress information for a running node."""

    node_id: str
    row: int
    total_rows: int
    result_key: str | None = None
    record_id: str | None = None


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

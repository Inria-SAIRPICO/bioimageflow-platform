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
    draft_revision: int | None = Field(default=None, ge=0)

    @field_validator("workflow_name")
    @classmethod
    def validate_workflow_name(cls, value: str) -> str:
        return validate_workflow_id(value)


class ExecutionContext(BaseModel):
    """Stable identity for one accepted execution."""

    execution_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    draft_revision: int | None = Field(default=None, ge=0)

    @field_validator("workflow_id")
    @classmethod
    def validate_workflow_id(cls, value: str) -> str:
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
    node_statuses: dict[str, NodeStatus] = Field(default_factory=dict)
    execution_id: str | None = None
    workflow_id: str | None = None
    draft_revision: int | None = None

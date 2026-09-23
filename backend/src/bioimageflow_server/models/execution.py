"""Execution models: requests, progress, results, and status."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bioimageflow_server.models.validation import NodeStatus
from bioimageflow_server.models.workflow import validate_workflow_id


class ExecutionRequest(BaseModel):
    """Execute one accepted root draft."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[str] | None = None
    workflow_id: str = Field(min_length=1)
    draft_revision: int = Field(
        ge=0,
        description=(
            "Current accepted root-draft revision to verify. Revision 0 is the "
            "non-historical view synthesized from the current saved workflow when "
            "no draft file exists."
        ),
    )
    mode: Literal["normal", "retry", "invalidate_failed", "recompute"] = "normal"
    retry_of_execution_id: str | None = Field(default=None, min_length=1)

    @field_validator("workflow_id")
    @classmethod
    def validate_workflow_name(cls, value: str) -> str:
        return validate_workflow_id(value)

    @model_validator(mode="after")
    def validate_execution_mode(self) -> "ExecutionRequest":
        retry_modes = {"retry", "invalidate_failed"}
        if self.mode in retry_modes and self.retry_of_execution_id is None:
            raise ValueError(f"retry_of_execution_id is required for mode '{self.mode}'")
        if self.mode in retry_modes and self.nodes is not None:
            raise ValueError(f"mode '{self.mode}' reuses the original execution targets")
        if self.mode not in retry_modes and self.retry_of_execution_id is not None:
            raise ValueError(f"retry_of_execution_id is not valid for mode '{self.mode}'")
        if self.mode == "recompute" and self.nodes is not None:
            raise ValueError("recompute always targets the complete enabled workflow")
        return self


class ExecutionContext(BaseModel):
    """Stable identity for one accepted execution."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    draft_revision: int = Field(ge=0)
    mode: Literal["normal", "retry", "invalidate_failed", "recompute"] = "normal"
    requested_nodes: list[str] | None = None
    retry_of_execution_id: str | None = None
    planned_node_ids: list[str] = Field(default_factory=list)
    planned_node_names: dict[str, str] = Field(default_factory=dict)

    @field_validator("workflow_id")
    @classmethod
    def validate_workflow_id(cls, value: str) -> str:
        return validate_workflow_id(value)


class ProgressInfo(BaseModel):
    """Progress information for a running node."""

    node_id: str
    status: Literal["row_progress", "row_complete"]
    row: int
    total_rows: int
    task_current: int | None = None
    task_maximum: int | None = None
    result_key: str | None = None
    record_id: str | None = None


class ExecutionResult(BaseModel):
    """Result of a graph execution."""

    success: bool
    errors: list[dict[str, Any]] = []
    node_statuses: dict[str, NodeStatus] = {}


class ExecutionStatus(BaseModel):
    """Current execution status of the engine."""

    state: Literal["starting", "running", "idle"]
    last_result: ExecutionResult | None = None
    progress: ProgressInfo | None = None
    node_statuses: dict[str, NodeStatus] = Field(default_factory=dict)
    execution_id: str | None = None
    workflow_id: str | None = None
    draft_revision: int | None = None
    mode: Literal["normal", "retry", "invalidate_failed", "recompute"] = "normal"
    requested_nodes: list[str] | None = None
    retry_of_execution_id: str | None = None
    planned_node_ids: list[str] = Field(default_factory=list)
    planned_node_names: dict[str, str] = Field(default_factory=dict)

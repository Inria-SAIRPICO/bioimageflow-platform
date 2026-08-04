"""Engine-neutral retained execution models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RunState = Literal[
    "preparing",
    "prepared",
    "queued",
    "starting",
    "running",
    "cancel_requested",
    "finalizing",
    "succeeded",
    "failed",
    "cancelled",
    "lost",
]
JobState = Literal[
    "waiting",
    "running",
    "cached",
    "succeeded",
    "failed",
    "cancelled",
    "skipped",
    "blocked",
]
ExecutionBackend = Literal[
    "direct",
    "wetlands",
    "attached_parsl",
    "submitted_local",
    "submitted_remote",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FailureDiagnosticSnapshot(BaseModel):
    """Secret-redacted failure associated with one scoped node attempt."""

    model_config = ConfigDict(extra="forbid")

    scoped_node_path: str = Field(min_length=1)
    category: str = Field(min_length=1)
    exception_type: str = Field(min_length=1)
    message: str
    traceback: str | None = None
    attempt_id: str | None = None
    retry_status: str = "terminal"
    terminal: bool = True


class JobSnapshot(BaseModel):
    """Latest reduced state for one scoped workflow node."""

    model_config = ConfigDict(extra="forbid")

    scoped_node_path: str = Field(min_length=1)
    state: JobState = "waiting"
    row: int = Field(default=0, ge=0)
    total_rows: int = Field(default=0, ge=0)
    current: int | None = Field(default=None, ge=0)
    maximum: int | None = Field(default=None, ge=0)
    message: str | None = None
    result_key: str | None = None
    record_id: str | None = None
    executor_label: str | None = None
    route_reason: str | None = None
    effective_resources: dict[str, Any] | None = None
    diagnostic: FailureDiagnosticSnapshot | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ObservationSnapshot(BaseModel):
    """Health of the platform's latest observation, separate from run state."""

    model_config = ConfigDict(extra="forbid")

    reachable: bool = True
    observed_at: datetime = Field(default_factory=utc_now)
    error: str | None = None


class ExecutionActionAvailability(BaseModel):
    """Capability- and state-derived availability for one execution action."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    reason: str | None = None


class ExecutionActions(BaseModel):
    """The complete action surface presented for a retained execution."""

    model_config = ConfigDict(extra="forbid")

    cancel: ExecutionActionAvailability
    retry: ExecutionActionAvailability
    recompute: ExecutionActionAvailability
    download_results: ExecutionActionAvailability


def unavailable_execution_actions() -> ExecutionActions:
    unavailable = ExecutionActionAvailability(
        available=False,
        reason="Execution actions have not been derived yet.",
    )
    return ExecutionActions(
        cancel=unavailable,
        retry=unavailable,
        recompute=unavailable,
        download_results=unavailable,
    )


class ResultExportSnapshot(BaseModel):
    """Durable availability of the managed immutable result bundle."""

    model_config = ConfigDict(extra="forbid")

    state: Literal["pending", "available", "unavailable"] = "pending"
    error_code: str | None = None
    detail: str | None = None


class ExecutionSnapshot(BaseModel):
    """Durable, revisioned presentation state for one execution."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    execution_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    draft_revision: int | None = Field(default=None, ge=0)
    graph_fingerprint: str | None = None
    command: Literal["run", "run_selected", "retry", "invalidate_retry", "recompute"] = "run"
    requested_nodes: list[str] | None = None
    retry_of_execution_id: str | None = None
    child_execution_ids: list[str] = Field(default_factory=list)
    backend: ExecutionBackend
    target_id: str
    profile_id: str | None = None
    profile_revision: int | None = Field(default=None, ge=0)
    target_snapshot: dict[str, Any] = Field(default_factory=dict)
    state: RunState
    jobs: dict[str, JobSnapshot] = Field(default_factory=dict)
    progress_cursor: int = Field(default=0, ge=0)
    reconnect: dict[str, Any] | None = None
    backend_metadata: dict[str, Any] = Field(default_factory=dict)
    actions: ExecutionActions = Field(default_factory=unavailable_execution_actions)
    result_export: ResultExportSnapshot = Field(default_factory=ResultExportSnapshot)
    observation: ObservationSnapshot = Field(default_factory=ObservationSnapshot)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None

    @field_validator("jobs")
    @classmethod
    def validate_job_keys(cls, value: dict[str, JobSnapshot]) -> dict[str, JobSnapshot]:
        for key, job in value.items():
            if key != job.scoped_node_path:
                raise ValueError("Job keys must equal their scoped node paths")
        return value

    @property
    def terminal(self) -> bool:
        return self.state in {"succeeded", "failed", "cancelled", "lost"}


class ExecutionPage(BaseModel):
    items: list[ExecutionSnapshot]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(gt=0)


class ExecutionUpdate(BaseModel):
    """WebSocket payload used for a complete, revisioned run replacement."""

    type: Literal["execution_snapshot", "execution_update"]
    snapshot: ExecutionSnapshot


class ExecutionActionResponse(BaseModel):
    execution_id: str
    accepted: bool = True
    state: RunState


class RecomputeSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    node_paths: tuple[str, ...] = Field(min_length=1)
    cascade: bool = True


class RetryInvalidationPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    node_path: str
    result_key: str
    record_id: str | None
    selection_status: Literal["selected", "corrupt"]


class RetryTargetPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    mode: Literal["local", "attached", "submitted_local", "submitted_remote"]


class RetryPlanPresentation(BaseModel):
    """Presentation-safe view of a persisted immutable BioImageFlow retry plan."""

    model_config = ConfigDict(extra="forbid")

    plan_digest: str
    parent_execution_id: str
    child_execution_id: str
    mode: Literal["retry", "recompute"]
    target: RetryTargetPresentation
    recompute: RecomputeSelection | None
    invalidations: list[RetryInvalidationPresentation]
    conflicting_run_ids: list[str]
    confirmable: bool
    disabled_reason: str | None = None


class RetryPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    recompute: RecomputeSelection | None


class ConfirmRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

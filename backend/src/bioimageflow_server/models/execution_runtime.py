"""Engine-neutral retained execution models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, cast

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
    "managed_remote",
]
ExecutionTargetMode = Literal["local", "managed_remote"]


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


class ClusterDiagnosticValue(BaseModel):
    """Public, secret-redacted managed cluster operation diagnostic."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    schema_: Literal["bioimageflow.cluster_diagnostic.v1"] = Field(alias="schema")
    phase: str
    category: str
    message: str
    allocation_state: Literal[
        "none", "orchestrator-submitted", "workers-possible", "unknown"
    ]
    retry_safety: Literal["safe", "same-attempt-only", "unsafe", "not-applicable"]
    next_action: str
    identities: dict[str, str] = Field(default_factory=dict)


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
    cleanup: ExecutionActionAvailability


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
        cleanup=unavailable,
    )


class ResultExportSnapshot(BaseModel):
    """Durable availability of the managed immutable result bundle."""

    model_config = ConfigDict(extra="forbid")

    state: Literal["pending", "available", "unavailable"] = "pending"
    error_code: str | None = None
    detail: str | None = None
    archive_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )


class ExecutionSnapshot(BaseModel):
    """Durable internal record for one execution; never serialize directly to clients."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
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
    diagnostics: list[ClusterDiagnosticValue] = Field(default_factory=list)
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


class ExecutionPresentation(BaseModel):
    """Explicit secret-free execution DTO used by HTTP and WebSocket clients."""

    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    execution_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    draft_revision: int | None = Field(default=None, ge=0)
    command: Literal["run", "run_selected", "retry", "invalidate_retry", "recompute"]
    retry_of_execution_id: str | None = None
    child_execution_ids: list[str] = Field(default_factory=list)
    backend: ExecutionBackend
    target_id: str
    target_label: str
    target_mode: ExecutionTargetMode
    scheduler_job_id: str | None = None
    state: RunState
    jobs: dict[str, JobSnapshot] = Field(default_factory=dict)
    progress_cursor: int = Field(default=0, ge=0)
    actions: ExecutionActions
    diagnostics: list[ClusterDiagnosticValue] = Field(default_factory=list)
    observation: ObservationSnapshot
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None


def present_execution(snapshot: ExecutionSnapshot) -> ExecutionPresentation:
    """Project a durable record onto the allowlisted public execution contract."""

    target_label = snapshot.target_snapshot.get("name")
    scheduler_job_id = snapshot.backend_metadata.get("scheduler_job_id")
    target_mode = cast(ExecutionTargetMode, {
        "direct": "local",
        "wetlands": "local",
        "managed_remote": "managed_remote",
    }[snapshot.backend])
    return ExecutionPresentation(
        revision=snapshot.revision,
        execution_id=snapshot.execution_id,
        workflow_id=snapshot.workflow_id,
        draft_revision=snapshot.draft_revision,
        command=snapshot.command,
        retry_of_execution_id=snapshot.retry_of_execution_id,
        child_execution_ids=snapshot.child_execution_ids,
        backend=snapshot.backend,
        target_id=snapshot.target_id,
        target_label=target_label if isinstance(target_label, str) else snapshot.target_id,
        target_mode=target_mode,
        scheduler_job_id=scheduler_job_id if isinstance(scheduler_job_id, str) else None,
        state=snapshot.state,
        jobs=snapshot.jobs,
        progress_cursor=snapshot.progress_cursor,
        actions=snapshot.actions,
        diagnostics=snapshot.diagnostics,
        observation=snapshot.observation,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
        finished_at=snapshot.finished_at,
    )


class ExecutionPage(BaseModel):
    """Internal page of durable execution records."""

    items: list[ExecutionSnapshot]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(gt=0)


class ExecutionPresentationPage(BaseModel):
    items: list[ExecutionPresentation]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(gt=0)


class ExecutionUpdate(BaseModel):
    """WebSocket payload used for a complete, revisioned run replacement."""

    type: Literal["execution_snapshot", "execution_update"]
    snapshot: ExecutionPresentation


class ExecutionActionResponse(BaseModel):
    execution_id: str
    accepted: bool = True
    state: RunState


class RecomputeSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    node_paths: list[str] = Field(min_length=1)
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
    mode: Literal["local", "managed_remote"]


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


class ExecutionCleanupPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    older_than_seconds: int = Field(default=86_400, ge=0)


class ExecutionCleanupPresentation(BaseModel):
    execution_id: str
    plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    plan: dict[str, Any]


class ConfirmExecutionCleanupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ExecutionCleanupReport(BaseModel):
    execution_id: str
    report: dict[str, Any]

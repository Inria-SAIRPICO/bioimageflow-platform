"""WebSocket message Pydantic models (server→client and client→server)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from bioimageflow_server.models.validation import NodeStatus
from bioimageflow_server.models.workflow_draft import DraftWriter


# --- Shared base ---


class _MessageBase(BaseModel):
    """Common config for every WS message — extras are rejected on both
    server→client and client→server payloads to catch typos early."""

    model_config = ConfigDict(extra="forbid")


# --- Server-to-client messages ---


class ProgressMessage(_MessageBase):
    type: Literal["progress"] = "progress"
    node_id: str
    status: str
    row: int
    total_rows: int
    timestamp: float
    result_key: str | None = None
    record_id: str | None = None
    execution_id: str
    workflow_id: str
    draft_revision: int | None = None


# Reuse NodeStatus's status literal so we do not redeclare the 6-value list here.
NodeStatusLiteral = NodeStatus.model_fields["status"].annotation


class NodeStateMessage(_MessageBase):
    type: Literal["node_state"] = "node_state"
    node_id: str
    status: NodeStatusLiteral  # type: ignore[valid-type]
    cached: bool
    error: str | None = None
    traceback: str | None = None
    result_key: str | None = None
    record_id: str | None = None
    execution_id: str
    workflow_id: str
    draft_revision: int | None = None


class LogMessage(_MessageBase):
    type: Literal["log"] = "log"
    level: str
    message: str
    node_id: str | None = None
    timestamp: float


class ExecutionCompleteMessage(_MessageBase):
    type: Literal["execution_complete"] = "execution_complete"
    success: bool
    errors: list[dict[str, Any]] = []
    node_statuses: dict[str, Any]
    execution_id: str
    workflow_id: str
    draft_revision: int | None = None


class StatusSnapshotMessage(_MessageBase):
    type: Literal["status_snapshot"] = "status_snapshot"
    state: Literal["running", "idle"]
    last_result: dict[str, Any] | None = None
    progress: dict[str, Any] | None = None
    node_statuses: dict[str, Any] = {}
    execution_id: str | None = None
    workflow_id: str | None = None
    draft_revision: int | None = None


class ToolReloadMessage(_MessageBase):
    type: Literal["tool_reload"] = "tool_reload"
    tool_name: str
    tool_metadata: dict[str, Any]


class ToolRemovedMessage(_MessageBase):
    type: Literal["tool_removed"] = "tool_removed"
    tool_name: str


class SystemErrorMessage(_MessageBase):
    type: Literal["system_error"] = "system_error"
    code: str
    detail: str
    timestamp: float


class PackageInstallMessage(_MessageBase):
    type: Literal["package_install"] = "package_install"
    package_name: str
    status: Literal["installing", "complete", "failed"]
    detail: str | None = None


class EnvironmentStatusMessage(_MessageBase):
    type: Literal["environment_status"] = "environment_status"
    env_name: str
    status: Literal["stopped", "creating", "running"]


class WorkflowDraftChangedMessage(_MessageBase):
    type: Literal["workflow_draft_changed"] = "workflow_draft_changed"
    workflow_id: str
    draft_revision: int
    updated_by: DraftWriter
    updated_at: str
    dirty_against_saved: bool


class AckMessage(_MessageBase):
    type: Literal["ack"] = "ack"
    ref: str


class ErrorMessage(_MessageBase):
    type: Literal["error"] = "error"
    ref: str | None = None
    code: str
    detail: str


# --- Client-to-server messages ---


class SubscribeLogsMessage(_MessageBase):
    type: Literal["subscribe_logs"] = "subscribe_logs"
    message_id: str | None = None
    node_id: str | None = None
    level: str | None = None


# --- Discriminated unions ---

ServerMessage = Annotated[
    Union[
        ProgressMessage,
        NodeStateMessage,
        LogMessage,
        ExecutionCompleteMessage,
        StatusSnapshotMessage,
        ToolReloadMessage,
        ToolRemovedMessage,
        SystemErrorMessage,
        PackageInstallMessage,
        EnvironmentStatusMessage,
        WorkflowDraftChangedMessage,
        AckMessage,
        ErrorMessage,
    ],
    Field(discriminator="type"),
]

ClientMessage = Annotated[
    Union[SubscribeLogsMessage],
    Field(discriminator="type"),
]


__all__ = [
    "AckMessage",
    "ClientMessage",
    "EnvironmentStatusMessage",
    "ErrorMessage",
    "ExecutionCompleteMessage",
    "LogMessage",
    "NodeStateMessage",
    "PackageInstallMessage",
    "ProgressMessage",
    "ServerMessage",
    "SubscribeLogsMessage",
    "SystemErrorMessage",
    "StatusSnapshotMessage",
    "ToolReloadMessage",
    "ToolRemovedMessage",
    "WorkflowDraftChangedMessage",
]

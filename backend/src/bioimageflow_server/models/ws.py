"""WebSocket message Pydantic models (server→client and client→server)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from bioimageflow_server.models.validation import NodeStatus


# --- Server-to-client messages ---


class _ServerMessageBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProgressMessage(_ServerMessageBase):
    type: Literal["progress"] = "progress"
    node_id: str
    status: str
    row: int
    total_rows: int
    timestamp: float


# Reuse NodeStatus's status literal so we do not redeclare the 6-value list here.
NodeStatusLiteral = NodeStatus.model_fields["status"].annotation


class NodeStateMessage(_ServerMessageBase):
    type: Literal["node_state"] = "node_state"
    node_id: str
    status: NodeStatusLiteral  # type: ignore[valid-type]
    cached: bool
    error: str | None = None
    traceback: str | None = None


class LogMessage(_ServerMessageBase):
    type: Literal["log"] = "log"
    level: str
    message: str
    node_id: str | None = None
    timestamp: float


class ExecutionCompleteMessage(_ServerMessageBase):
    type: Literal["execution_complete"] = "execution_complete"
    success: bool
    errors: list[dict[str, Any]] = []
    node_statuses: dict[str, Any]


class ToolReloadMessage(_ServerMessageBase):
    type: Literal["tool_reload"] = "tool_reload"
    tool_name: str
    tool_metadata: dict[str, Any]


class PackageInstallMessage(_ServerMessageBase):
    type: Literal["package_install"] = "package_install"
    package_name: str
    status: Literal["installing", "complete", "failed"]
    detail: str | None = None


class EnvironmentStatusMessage(_ServerMessageBase):
    type: Literal["environment_status"] = "environment_status"
    env_name: str
    status: Literal["stopped", "creating", "running"]


class AckMessage(_ServerMessageBase):
    type: Literal["ack"] = "ack"
    ref: str


class ErrorMessage(_ServerMessageBase):
    type: Literal["error"] = "error"
    ref: str | None = None
    code: str
    detail: str


# --- Client-to-server messages ---


class SubscribeLogsMessage(_ServerMessageBase):
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
        ToolReloadMessage,
        PackageInstallMessage,
        EnvironmentStatusMessage,
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
    "ToolReloadMessage",
]

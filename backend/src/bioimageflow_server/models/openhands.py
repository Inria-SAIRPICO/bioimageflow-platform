"""OpenHands API models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OpenHandsApproval(BaseModel):
    """User-visible approval request created by the agent bridge."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str = "package_install"
    package_name: str
    package_version: str | None = None
    command: str | None = None
    status: str = "pending"


class OpenHandsStatus(BaseModel):
    """Runtime status for the owned OpenHands process."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    running: bool
    pid: int | None = None
    url: str | None = None
    reason: str | None = None
    installed: bool = False
    configured: bool = False
    setup_state: str = "missing"
    approvals: list[OpenHandsApproval] = Field(default_factory=list)


class OpenHandsContext(BaseModel):
    """Effective OpenHands configuration exposed to frontend callers."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    reason: str | None = None
    deployment_mode: str
    unsafe_webapp_features_enabled: bool
    runtime: str
    host: str
    port: int
    url: str
    workspace: str
    process_acknowledged: bool


class OpenHandsConfig(BaseModel):
    """Minimal frontend-editable OpenHands configuration."""

    model_config = ConfigDict(extra="forbid")

    installed: bool
    configured: bool
    command: str
    message: str | None = None


class OpenHandsConfigUpdate(BaseModel):
    """Editable OpenHands configuration fields."""

    model_config = ConfigDict(extra="forbid")

    command: str


class OpenHandsUndoRequest(BaseModel):
    """Undo the last applied agent proposal for a draft."""

    model_config = ConfigDict(extra="forbid")

    draft_id: str
    base_revision: int

"""OpenHands API models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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

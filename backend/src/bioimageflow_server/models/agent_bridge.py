"""Agent bridge request and response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentContextResponse(BaseModel):
    """Agent workspace context."""

    model_config = ConfigDict(extra="forbid")

    workflows_root: str
    platform_reference: str
    context_file: str


class AgentToolWriteRequest(BaseModel):
    """Write a workflow-local tool file."""

    model_config = ConfigDict(extra="forbid")

    path: str
    content: str


class AgentToolWriteResponse(BaseModel):
    """Workflow-local tool write result."""

    model_config = ConfigDict(extra="forbid")

    path: str


class AgentPackageInstallRequestCreate(BaseModel):
    """Create a package install approval request."""

    model_config = ConfigDict(extra="forbid")

    package_name: str
    version: str | None = None


class AgentPackageInstallRequestResponse(AgentPackageInstallRequestCreate):
    """Package install approval request state."""

    id: str
    approved: bool


class AgentPackageInstallApproveResponse(BaseModel):
    """Package install approval result."""

    model_config = ConfigDict(extra="forbid")

    status: str

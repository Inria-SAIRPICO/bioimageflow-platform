"""Workflow management models."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from bioimageflow_server.models.graph import GraphState


_WORKFLOW_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


class WorkflowCreate(BaseModel):
    """Request body for POST /workflows."""

    name: str
    display_name: str | None = None
    description: str | None = None
    storage_path: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not _WORKFLOW_NAME_RE.fullmatch(value):
            raise ValueError(
                "Workflow name must start with an alphanumeric character "
                "and contain only letters, numbers, underscores, or hyphens"
            )
        return value


class WorkflowInfo(BaseModel):
    """Workflow list item returned by GET /workflows."""

    name: str
    display_name: str
    path: str
    last_modified: str
    description: str | None = None
    storage_path: str | None = None


class WorkflowUpdate(BaseModel):
    """Request body for PATCH /workflows/{name}."""

    action: Literal["update", "duplicate"]
    display_name: str | None = None
    description: str | None = None
    new_name: str | None = None
    storage_path: str | None = None


class WorkflowSaveBody(BaseModel):
    """Request body for PUT /workflows/{name}."""

    graph: GraphState


class MissingPackage(BaseModel):
    """Package/version-level load issue for a workflow."""

    package_name: str
    required_version: str
    installed_versions: list[str] = Field(default_factory=list)
    affected_nodes: list[str] = Field(default_factory=list)


class MissingTool(BaseModel):
    """Node/tool-level load issue for a workflow."""

    node_id: str
    tool_name: str
    package_name: str | None = None
    required_version: str | None = None
    installed_versions: list[str] = Field(default_factory=list)


class WorkflowFile(BaseModel):
    """Workflow file response returned to the frontend."""

    info: WorkflowInfo
    graph: GraphState
    gui: dict[str, Any] = Field(default_factory=dict)
    missing_packages: list[MissingPackage] = Field(default_factory=list)
    missing_tools: list[MissingTool] = Field(default_factory=list)

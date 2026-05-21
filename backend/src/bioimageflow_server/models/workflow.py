"""Workflow management models."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from bioimageflow_server.models.graph import GraphState


_WORKFLOW_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def validate_workflow_id(value: str) -> str:
    """Validate a workspace-relative workflow or folder path."""
    normalized = value.strip().replace("\\", "/").strip("/")
    raw_segments = normalized.split("/")
    segments = [segment for segment in raw_segments if segment]
    if (
        not segments
        or len(raw_segments) != len(segments)
        or value.strip().startswith(("/", "\\"))
        or ".." in segments
    ):
        raise ValueError(
            "Workflow path must be a workspace-relative path of safe names"
        )
    for segment in segments:
        if not _WORKFLOW_NAME_RE.fullmatch(segment):
            raise ValueError(
                "Workflow name must start with an alphanumeric character "
                "and contain only letters, numbers, underscores, or hyphens"
            )
    return "/".join(segments)


def canonical_workflow_name(value: str) -> str:
    """Return the workflow ID generated from a user-facing display name."""
    ascii_value = (
        unicodedata.normalize("NFKD", value.strip()).encode("ascii", "ignore").decode("ascii")
    )
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value)
    normalized = re.sub(r"_+", "_", normalized).strip("_").lower()
    return WorkflowCreate(name=normalized).name


class WorkflowCreate(BaseModel):
    """Request body for POST /workflows."""

    name: str
    display_name: str | None = None
    description: str | None = None
    storage_path: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_workflow_id(value)


class WorkflowInfo(BaseModel):
    """Workflow list item returned by GET /workflows."""

    id: str | None = None
    name: str
    folder: str = ""
    display_name: str
    path: str
    last_modified: str
    description: str | None = None
    storage_path: str | None = None
    workspace_path: str | None = None
    output_path: str | None = None


class WorkflowUpdate(BaseModel):
    """Request body for PATCH /workflows/{name}."""

    action: Literal["update", "duplicate"]
    display_name: str | None = None
    description: str | None = None
    new_name: str | None = None
    folder: str | None = None
    new_id: str | None = None
    storage_path: str | None = None


class WorkflowFolderCreate(BaseModel):
    path: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return validate_workflow_id(value)


class WorkflowFolderUpdate(BaseModel):
    new_path: str

    @field_validator("new_path")
    @classmethod
    def validate_new_path(cls, value: str) -> str:
        return validate_workflow_id(value)


class WorkflowFolderDelete(BaseModel):
    policy: Literal["empty", "delete_children", "move_children_up"] = "empty"


class WorkflowFolderInfo(BaseModel):
    path: str
    display_name: str
    folders: list["WorkflowFolderInfo"] = Field(default_factory=list)
    workflows: list[WorkflowInfo] = Field(default_factory=list)


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


class RequiredPackage(BaseModel):
    """Package/version requirement recorded in a portable export."""

    name: str
    version: str


class LocalToolReference(BaseModel):
    """Reference to a local/custom tool that cannot be exported portably yet."""

    tool_name: str
    node_ids: list[str] = Field(default_factory=list)
    reason: Literal["custom_tool_not_portable"] = "custom_tool_not_portable"


class ExportedWorkflow(BaseModel):
    """Raw persisted workflow sections carried by a portable export."""

    name: str
    display_name: str
    description: str | None = None
    storage_path: str | None = None
    graph: dict[str, Any]
    library: dict[str, Any]
    gui: dict[str, Any]
    metadata: dict[str, Any]


class WorkflowExportDocument(BaseModel):
    """Portable workflow export file."""

    bioimageflow_export: Literal[True] = True
    export_version: Literal["1.0"] = "1.0"
    exported_at: str
    workflow: ExportedWorkflow
    required_packages: list[RequiredPackage] = Field(default_factory=list)
    local_tools: list[LocalToolReference] = Field(default_factory=list)


class WorkflowImportResponse(BaseModel):
    """Workflow import success response."""

    info: WorkflowInfo
    missing_packages: list[MissingPackage] = Field(default_factory=list)
    missing_tools: list[MissingTool] = Field(default_factory=list)


class WorkflowImportConflictResponse(BaseModel):
    """Workflow import conflict response."""

    error: Literal["conflict"] = "conflict"
    detail: str
    suggested_name: str


class WorkflowFile(BaseModel):
    """Workflow file response returned to the frontend."""

    info: WorkflowInfo
    graph: GraphState
    gui: dict[str, Any] = Field(default_factory=dict)
    missing_packages: list[MissingPackage] = Field(default_factory=list)
    missing_tools: list[MissingTool] = Field(default_factory=list)

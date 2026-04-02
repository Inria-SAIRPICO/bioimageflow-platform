"""Workflow management models."""

from typing import Any, Literal

from pydantic import BaseModel


class WorkflowCreate(BaseModel):
    """Request body for POST /workflows."""

    name: str
    display_name: str | None = None
    description: str | None = None
    storage_path: str | None = None


class WorkflowInfo(BaseModel):
    """Workflow list item returned by GET /workflows."""

    name: str
    display_name: str
    path: str
    last_modified: str
    description: str | None = None


class WorkflowUpdate(BaseModel):
    """Request body for PATCH /workflows/{name}."""

    action: Literal["update", "duplicate"]
    display_name: str | None = None
    description: str | None = None
    new_name: str | None = None
    storage_path: str | None = None


class WorkflowFile(BaseModel):
    """Persistence format for saved workflows."""

    workflow: dict[str, Any]
    gui: dict[str, Any]

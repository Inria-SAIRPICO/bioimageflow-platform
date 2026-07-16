"""Workflow draft API models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import ValidationResult


DraftWriter = Literal["frontend", "agent", "system"]


class WorkflowDraftPutRequest(BaseModel):
    """Request body for replacing the live workflow draft."""

    model_config = ConfigDict(populate_by_name=True)

    graph: GraphState
    expected_revision: int
    updated_by: DraftWriter = "frontend"
    validate_: bool = Field(default=True, alias="validate")


class WorkflowDraftResetRequest(BaseModel):
    """Request an atomic reset of the accepted draft to the saved artifact."""

    expected_revision: int
    updated_by: DraftWriter = "frontend"


class WorkflowDraftResponse(BaseModel):
    """Live workflow draft returned by the draft API."""

    draft_version: Literal[1] = 1
    workflow_id: str
    base_saved_revision: str
    draft_revision: int
    updated_at: str
    updated_by: DraftWriter
    dirty_against_saved: bool
    graph: GraphState
    validation: ValidationResult


class WorkflowDraftConflictResponse(BaseModel):
    """Machine-readable optimistic concurrency conflict."""

    error: Literal["draft_revision_conflict"] = "draft_revision_conflict"
    detail: str
    expected_revision: int
    current_revision: int
    current_updated_by: DraftWriter
    current_updated_at: str


class WorkflowDraftLockedResponse(BaseModel):
    """Machine-readable lock response while execution is running."""

    error: Literal["workflow_locked"] = "workflow_locked"
    detail: str

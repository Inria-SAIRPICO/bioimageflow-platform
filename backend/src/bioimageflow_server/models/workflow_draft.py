"""Workflow draft request and response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import ValidationResult


class WorkflowDraftCreate(BaseModel):
    """Request body for POST /workflow-drafts."""

    graph: GraphState = Field(default_factory=lambda: GraphState(nodes=[], edges=[]))
    workflow_name: str | None = None


class WorkflowDraftUpdate(BaseModel):
    """Request body for PUT /workflow-drafts/{draft_id}."""

    graph: GraphState
    base_revision: int
    client_seq: int | None = None


class WorkflowDraftParameterPatch(BaseModel):
    """Request body for PATCH /workflow-drafts/{draft_id}/nodes/{node_id}/parameters."""

    parameters: dict[str, Any]
    base_revision: int
    client_seq: int | None = None


class WorkflowDraftState(BaseModel):
    """Stored draft state returned by GET /workflow-drafts/{draft_id}."""

    draft_id: str
    revision: int
    graph: GraphState
    workflow_name: str | None = None
    client_seq: int | None = None
    dirty: bool = False


class WorkflowDraftResponse(WorkflowDraftState):
    """Draft mutation response with validation attached."""

    validation: ValidationResult

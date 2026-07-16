"""Models for durable private nested-workflow snapshots."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import ValidationResult


class NestedSnapshotOwner(BaseModel):
    """Hierarchical identity of the canvas that owns a nested editor."""

    kind: Literal["root", "nested"]
    canvas_id: str | None = Field(default=None, min_length=1)
    workflow_id: str | None = None
    session_id: UUID | None = None

    @model_validator(mode="after")
    def validate_owner(self) -> NestedSnapshotOwner:
        if self.kind == "root":
            if self.canvas_id is None:
                raise ValueError("Root nested snapshot owners require canvas_id")
            if self.session_id is not None:
                raise ValueError("Root nested snapshot owners cannot carry session_id")
        else:
            if self.session_id is None:
                raise ValueError("Nested snapshot owners require session_id")
            if self.canvas_id is not None or self.workflow_id is not None:
                raise ValueError(
                    "Nested snapshot owners are identified only by parent session_id"
                )
        return self


class NestedWorkflowSnapshotOpenRequest(BaseModel):
    """Resolve or create the private snapshot for one parent node."""

    owner: NestedSnapshotOwner
    parent_node_id: str = Field(min_length=1)
    graph: GraphState


class NestedWorkflowSnapshotPutRequest(BaseModel):
    """Revision-checked replacement of a private nested snapshot."""

    expected_revision: int = Field(ge=0)
    graph: GraphState


class NestedWorkflowSnapshotResponse(BaseModel):
    """One accepted, validated private nested-workflow document."""

    snapshot_version: Literal[1] = 1
    session_id: UUID
    owner: NestedSnapshotOwner
    parent_node_id: str
    snapshot_revision: int
    updated_at: str
    graph: GraphState
    validation: ValidationResult


class NestedWorkflowSnapshotConflictResponse(BaseModel):
    """Machine-readable optimistic revision conflict."""

    error: Literal["nested_snapshot_revision_conflict"] = (
        "nested_snapshot_revision_conflict"
    )
    detail: str
    expected_revision: int
    current_revision: int


class NestedWorkflowSnapshotDependencyConflictResponse(BaseModel):
    """Machine-readable conflict for snapshots that still own child sessions."""

    error: Literal["nested_snapshot_has_dependents"] = (
        "nested_snapshot_has_dependents"
    )
    detail: str
    dependent_session_ids: list[UUID]


class NestedWorkflowSnapshotLockedResponse(BaseModel):
    """Machine-readable global execution lock response."""

    error: Literal["workflow_locked"] = "workflow_locked"
    detail: str

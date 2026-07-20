"""Revisioned source refresh and trusted Python materialization models."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from bioimageflow_server.models.graph import GraphState


class SourceOperationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkflowSourceUpdatePreviewRequest(SourceOperationModel):
    workflow_path: list[str] = Field(min_length=1)
    expected_artifact_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SourceDestructiveEffect(SourceOperationModel):
    kind: Literal["removed_input", "changed_input", "removed_output", "changed_output"]
    port_id: str
    affected_edge_ids: list[str] = Field(default_factory=list)
    affected_binding: bool = False


class WorkflowSourcePreview(SourceOperationModel):
    token: UUID
    operation: Literal["source_update", "python_rebuild"]
    workflow_id: str
    workflow_path: list[str] = Field(default_factory=list)
    parent_artifact_hash: str
    source_artifact_hash: str
    destructive_effects: list[SourceDestructiveEffect] = Field(default_factory=list)
    custom_source_ids_added: list[str] = Field(default_factory=list)
    custom_source_ids_removed: list[str] = Field(default_factory=list)
    replacement: GraphState


class WorkflowSourceApplyRequest(SourceOperationModel):
    token: UUID
    confirm_effects: list[SourceDestructiveEffect] = Field(default_factory=list)


class PythonSourcePreviewRequest(SourceOperationModel):
    expected_artifact_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class WorkflowSourceApplyResponse(SourceOperationModel):
    graph: GraphState
    artifact_hash: str

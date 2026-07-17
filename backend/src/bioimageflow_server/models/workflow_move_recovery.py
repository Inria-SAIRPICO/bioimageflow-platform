"""Strict durable record for interrupted workflow identity moves."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bioimageflow_server.models.workflow import validate_workflow_id

WorkflowMoveKind = Literal[
    "direct_workflow_move",
    "folder_rename",
    "folder_promotion",
]
WorkflowMovePhase = Literal[
    "prepared",
    "artifacts_rewritten",
    "snapshots_rewritten",
]


def _validate_relative_path(value: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return value
    if not value or value in (".", "..") or "\\" in value:
        raise ValueError("Move journal paths must be non-empty POSIX-relative paths")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("Move journal paths must stay below their configured root")
    if path.as_posix() != value:
        raise ValueError("Move journal paths must be canonical POSIX-relative paths")
    return value


class WorkflowManagedStorageMove(BaseModel):
    """Managed output directory transition captured before mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_path: str = Field(min_length=1)
    destination_path: str = Field(min_length=1)
    source_existed: bool

    @model_validator(mode="after")
    def validate_distinct_paths(self) -> WorkflowManagedStorageMove:
        if self.source_path == self.destination_path:
            raise ValueError("Managed storage move requires distinct paths")
        return self


class WorkflowArtifactMove(BaseModel):
    """One workflow identity and its exact intended durable metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_workflow_id: str = Field(min_length=1)
    destination_workflow_id: str = Field(min_length=1)
    source_generation_before: int = Field(ge=0)
    source_generation_after: int = Field(ge=1)
    destination_generation_before: int = Field(ge=0)
    destination_generation_after: int = Field(ge=1)
    target_metadata: dict[str, Any]
    managed_storage: WorkflowManagedStorageMove | None = None

    @model_validator(mode="after")
    def validate_identity_transition(self) -> WorkflowArtifactMove:
        if validate_workflow_id(self.source_workflow_id) != self.source_workflow_id:
            raise ValueError("Source workflow id must be canonical")
        if validate_workflow_id(self.destination_workflow_id) != self.destination_workflow_id:
            raise ValueError("Destination workflow id must be canonical")
        if self.source_workflow_id == self.destination_workflow_id:
            raise ValueError("Workflow move identities must be distinct")
        if self.source_generation_after != self.source_generation_before + 1:
            raise ValueError("Source workflow generation must advance exactly once")
        if self.destination_generation_after != self.destination_generation_before + 1:
            raise ValueError("Destination workflow generation must advance exactly once")
        return self


class WorkflowPromotionChildMove(BaseModel):
    """One immediate child promoted relative to the workflows root."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_relative_path: str = Field(min_length=1)
    destination_relative_path: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_paths(self) -> WorkflowPromotionChildMove:
        _validate_relative_path(self.source_relative_path)
        _validate_relative_path(self.destination_relative_path)
        if self.source_relative_path == self.destination_relative_path:
            raise ValueError("Promotion child paths must be distinct")
        return self


class WorkflowMoveJournal(BaseModel):
    """One exclusive, forward-recoverable workspace move operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    journal_version: Literal[1] = 1
    operation_id: UUID
    operation_kind: WorkflowMoveKind
    phase: WorkflowMovePhase = "prepared"
    source_path: str = Field(min_length=1)
    destination_path: str
    moves: list[WorkflowArtifactMove]
    promotion_children: list[WorkflowPromotionChildMove] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_operation_shape(self) -> WorkflowMoveJournal:
        _validate_relative_path(self.source_path)
        _validate_relative_path(
            self.destination_path,
            allow_empty=self.operation_kind == "folder_promotion",
        )
        if validate_workflow_id(self.source_path) != self.source_path:
            raise ValueError("Move journal source path must be canonical")
        if self.destination_path and (
            validate_workflow_id(self.destination_path) != self.destination_path
        ):
            raise ValueError("Move journal destination path must be canonical")

        source_ids = [move.source_workflow_id for move in self.moves]
        destination_ids = [move.destination_workflow_id for move in self.moves]
        affected_ids = [*source_ids, *destination_ids]
        if len(set(affected_ids)) != len(affected_ids):
            raise ValueError("Move journal workflow identities must be unique")

        if self.operation_kind == "direct_workflow_move":
            if len(self.moves) != 1 or self.promotion_children:
                raise ValueError("Direct workflow move requires exactly one workflow mapping")
            move = self.moves[0]
            if (
                self.source_path != move.source_workflow_id
                or self.destination_path != move.destination_workflow_id
            ):
                raise ValueError("Direct workflow paths must match its identity mapping")
        elif self.operation_kind == "folder_rename":
            if self.promotion_children:
                raise ValueError("Folder rename cannot carry promotion child mappings")
            if self.source_path == self.destination_path:
                raise ValueError("Folder rename paths must be distinct")
        elif not self.promotion_children:
            raise ValueError("Folder promotion requires explicit immediate-child mappings")

        if self.operation_kind == "folder_promotion":
            source_prefix = f"{self.source_path}/"
            destination_prefix = f"{self.destination_path}/" if self.destination_path else ""
            for child in self.promotion_children:
                if not child.source_relative_path.startswith(source_prefix):
                    raise ValueError("Promotion child must originate in the removed folder")
                source_suffix = child.source_relative_path[len(source_prefix) :]
                if "/" in source_suffix:
                    raise ValueError("Promotion mappings must describe immediate children")
                if child.destination_relative_path != f"{destination_prefix}{source_suffix}":
                    raise ValueError("Promotion destination must preserve the child name")
        return self

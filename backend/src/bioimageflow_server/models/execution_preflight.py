"""Requests and discriminated responses for distributed execution preflight."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RemotePathLeaf(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["upload", "cluster", "none"]
    value: str | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "RemotePathLeaf":
        if self.source == "none" and self.value is not None:
            raise ValueError("none path choices cannot contain a value")
        if self.source != "none" and not self.value:
            raise ValueError(f"{self.source} path choices require a value")
        return self


class ExecutionPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1)
    draft_revision: int = Field(ge=0)
    target_id: str = Field(min_length=1)
    profile_revision: int = Field(ge=1)
    requested_nodes: list[str] | None = None
    node_path_choices: dict[str, dict[str, Any]] = Field(default_factory=dict)


class RemoteNodePathInputValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scoped_node_path: str = Field(min_length=1)
    input_name: str = Field(min_length=1)
    value_shape: Literal["path", "list", "tuple"]
    nullable: bool
    path_picker: str | None = None
    current_paths: list[str] = Field(default_factory=list)
    cluster_compatible: bool


class RemoteNodePathPlanValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_: Literal["bioimageflow.remote_node_path_plan.v1"] = Field(
        alias="schema",
        serialization_alias="schema",
    )
    allocates_resources: Literal[False]
    reads_local_files: Literal[False]
    inputs: list[RemoteNodePathInputValue]


class ResolutionRequiredPreflight(BaseModel):
    kind: Literal["resolution_required"] = "resolution_required"
    remote_node_paths: RemoteNodePathPlanValue
    unresolved: list[dict[str, str]]


class ReadyPreflight(BaseModel):
    kind: Literal["ready"] = "ready"
    token: str | None = None
    expires_at: float | None = None
    resolved_inputs: int = Field(default=0, ge=0)


ExecutionPreflightResponse = ResolutionRequiredPreflight | ReadyPreflight


class ApplyPreparedExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    draft_revision: int = Field(ge=0)
    target_id: str = Field(min_length=1)
    requested_nodes: list[str] | None = None

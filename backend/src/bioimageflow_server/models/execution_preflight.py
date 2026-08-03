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
    requested_nodes: list[str] | None = None
    root_inputs: dict[str, Any] = Field(default_factory=dict)
    node_path_choices: dict[str, dict[str, Any]] = Field(default_factory=dict)
    node_routes: dict[str, str] = Field(default_factory=dict)


class ResolutionRequiredPreflight(BaseModel):
    kind: Literal["resolution_required"] = "resolution_required"
    distributed_plan: dict[str, Any]
    remote_node_paths: dict[str, Any]
    unresolved: list[dict[str, str]]


class ReadyPreflight(BaseModel):
    kind: Literal["ready"] = "ready"
    token: str | None = None
    expires_at: float | None = None
    distributed_plan: dict[str, Any]
    manifest: dict[str, Any] | None = None


ExecutionPreflightResponse = ResolutionRequiredPreflight | ReadyPreflight


class ApplyPreparedExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    draft_revision: int = Field(ge=0)
    target_id: str = Field(min_length=1)
    requested_nodes: list[str] | None = None


class RetryExecutionRequest(BaseModel):
    target_id: str | None = None


class ResultDownloadRequest(BaseModel):
    destination: str = Field(min_length=1)

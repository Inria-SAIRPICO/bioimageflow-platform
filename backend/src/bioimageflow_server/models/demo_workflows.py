"""Bundled demo workflow API models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DemoWorkflowStatus(BaseModel):
    id: str
    version: int = Field(ge=1)
    workflow_id: str
    display_name: str
    status: Literal["installed", "missing", "conflict"]
    installed_version: int | None = Field(default=None, ge=1)
    identity_generation: int | None = Field(default=None, ge=0)


class DemoWorkflowsStatus(BaseModel):
    bundle_version: int = Field(ge=1)
    status: Literal["installed", "partial", "missing", "conflict"]
    workflows: list[DemoWorkflowStatus]
    can_install: bool
    can_remove: bool

"""Workspace API models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WorkspaceInfo(BaseModel):
    workspace_path: str
    workflows_root: str
    tools_root: str
    outputs_root: str
    deployment_mode: Literal["desktop", "webapp"]
    user_editable: bool


class WorkspaceUpdate(BaseModel):
    workspace_path: str

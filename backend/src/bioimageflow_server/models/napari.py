"""Napari viewer integration models."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator

from bioimageflow_server.models.results import ResultArtifactIdentity


class NapariOpenRequest(BaseModel):
    """Body for ``POST /napari/open``."""

    paths: list[str]
    clear_layers: bool = False
    environment_id: UUID | None = None
    reader_id: str | None = None
    node_id: str | None = None
    row: int | None = None
    col: str | None = None
    workflow_name: str | None = None
    result_identity: ResultArtifactIdentity | None = None

    @field_validator("reader_id", mode="before")
    @classmethod
    def _normalize_reader_id(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class NapariLaunchRequest(BaseModel):
    """Start or focus one registered environment without opening an artifact."""

    environment_id: UUID


class NapariStatus(BaseModel):
    """Response for ``GET /napari/status``."""

    running: bool
    env_path: str | None = None
    pid: int | None = None


class NapariEnvironmentStatus(NapariStatus):
    """Lifecycle state for one explicitly registered environment."""

    environment_id: UUID
    environment_name: str
    installation_identity: str
    status: Literal["stopped", "opening", "running", "failed", "restart_required"]
    detail: str | None = None

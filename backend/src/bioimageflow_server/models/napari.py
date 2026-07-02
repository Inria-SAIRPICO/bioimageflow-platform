"""Napari viewer integration models."""

from __future__ import annotations

from pydantic import BaseModel


class NapariOpenRequest(BaseModel):
    """Body for ``POST /napari/open``."""

    paths: list[str]
    clear_layers: bool = False
    node_id: str | None = None
    row: int | None = None
    col: str | None = None
    workflow_name: str | None = None


class NapariStatus(BaseModel):
    """Response for ``GET /napari/status``."""

    running: bool
    env_path: str | None = None
    pid: int | None = None

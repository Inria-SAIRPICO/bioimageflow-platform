"""Fiji viewer integration models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FijiOpenRequest(BaseModel):
    """Select one workflow result image to open in Fiji."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    row: int = Field(ge=0)
    col: str
    workflow_name: str | None = None

    @field_validator("node_id", "col", mode="before")
    @classmethod
    def _trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("node_id", "col")
    @classmethod
    def _require_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value must be non-empty")
        return value

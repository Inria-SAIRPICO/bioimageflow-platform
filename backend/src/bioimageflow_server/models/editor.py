"""Editor API models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator


class EditorOpenMethod(StrEnum):
    EXTERNAL = "external"
    EMBEDDED = "embedded"
    CLIPBOARD = "clipboard"


class EditorStatus(BaseModel):
    available: bool
    url: str | None = None
    version: str | None = None
    control_available: bool = False


class EditorOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str

    @field_validator("path")
    @classmethod
    def _path_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path must not be empty")
        return value


class EditorOpenResponse(BaseModel):
    opened: bool
    method: EditorOpenMethod
    url: str | None = None
    path: str
    message: str | None = None

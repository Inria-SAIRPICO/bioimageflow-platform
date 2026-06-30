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
    launch_attempted: bool = False
    error_code: str | None = None
    error_detail: str | None = None


class EditorOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    focus_path: str | None = None

    @field_validator("path")
    @classmethod
    def _path_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path must not be empty")
        return value

    @field_validator("focus_path")
    @classmethod
    def _focus_path_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("focus_path must not be empty")
        return value


class EditorOpenToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    workflow_name: str | None = None
    workflow_id: str | None = None

    @field_validator("tool_name")
    @classmethod
    def _tool_name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("tool_name must not be empty")
        return value


class EditorOpenResponse(BaseModel):
    opened: bool
    method: EditorOpenMethod
    url: str | None = None
    path: str
    message: str | None = None
    error_code: str | None = None
    error_detail: str | None = None

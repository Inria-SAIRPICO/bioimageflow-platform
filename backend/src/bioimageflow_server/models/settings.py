"""Application settings models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_DEFAULT_MAX_UPLOAD_SIZE = 2 * 1024**3  # 2 GB (v1 §2.4.10)


class OMEROInstance(BaseModel):
    """OMERO server connection configuration."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    host: str
    port: int = Field(default=4064, ge=1, le=65535)
    username: str

    @field_validator("name", mode="before")
    @classmethod
    def _trim_optional_name(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("host", "username", mode="before")
    @classmethod
    def _trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("host", "username")
    @classmethod
    def _require_non_empty_text(cls, value: str) -> str:
        if not value:
            raise ValueError("OMERO host and username must be non-empty")
        return value

    def effective_name(self) -> str:
        """Return the display name used for uniqueness checks."""
        return self.name or f"{self.host}:{self.username}"


class OMEROInstancePatch(OMEROInstance):
    """API-facing OMERO instance patch with transient password input."""

    password: str | None = None


class OMEROInstanceResponse(OMEROInstance):
    """API-facing OMERO instance response with non-secret password state."""

    password_stored: bool


class Settings(BaseModel):
    """Application settings from GET/PATCH /settings.

    The model rejects unknown fields (``extra="forbid"``) so typos in PATCH
    bodies surface as 422s rather than being silently dropped. ``dev_mode``
    is permissive at the model layer; the GUI router rejects ``dev_mode=False``.
    """

    model_config = ConfigDict(extra="forbid")

    deployment_mode: Literal["desktop", "webapp"]
    external_editor: str | None = None
    fiji_path: str | None = None
    omero_instances: list[OMEROInstance] = []
    tool_store_path: str = "~/.bioimageflow/tool_packages/"
    update_mode: Literal["auto", "manual"] | str = "auto"
    execution_engine: Literal["sequential", "parallel"] = "sequential"
    new_workflow_execution: Literal["sequential", "parallel"] = "sequential"
    default_execution_target_id: str = "local"
    node_data_page_size: Literal[25, 50, 100, 250, 500] = 250
    keyboard_shortcuts: dict[str, str] = {}
    dev_mode: bool = True
    enable_unsafe_webapp_features: bool = False
    datasets_root: str | None = None
    max_upload_size: int = _DEFAULT_MAX_UPLOAD_SIZE
    workspace_path: str | None = None
    workspaces_root: str | None = None

    @field_validator("fiji_path", mode="before")
    @classmethod
    def _normalize_fiji_path(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="before")
    @classmethod
    def _synchronize_execution_preferences(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        legacy = payload.get("execution_engine")
        if legacy == "parsl":
            legacy = "parallel"
            payload["execution_engine"] = legacy
        preferred = payload.get("new_workflow_execution")
        if legacy is not None and preferred is None:
            payload["new_workflow_execution"] = legacy
        elif preferred is not None and legacy is None:
            payload["execution_engine"] = preferred
        elif legacy is not None and preferred is not None and legacy != preferred:
            raise ValueError("execution_engine and new_workflow_execution must match")
        return payload

    @field_validator("execution_engine", mode="before")
    @classmethod
    def _migrate_legacy_execution_engine(cls, value: object) -> object:
        if value == "parsl":
            return "parallel"
        return value

    @field_validator("default_execution_target_id", mode="before")
    @classmethod
    def _normalize_default_target(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("default_execution_target_id must be non-empty")
        return value

    @model_validator(mode="after")
    def _validate_unique_omero_instance_names(self) -> "Settings":
        seen: set[str] = set()
        for instance in self.omero_instances:
            effective_name = instance.effective_name()
            if effective_name in seen:
                raise ValueError("OMERO instance names must be unique")
            seen.add(effective_name)
        return self

"""Application settings models."""

from __future__ import annotations

import posixpath
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_DEFAULT_MAX_UPLOAD_SIZE = 2 * 1024**3  # 2 GB (v1 §2.4.10)
_DEFAULT_OUTPUT_DATA_FOLDER = "~/bioimageflow_data/"
_CACHE_MAX_AGE_PATTERN = re.compile(r"^\d+[smhd]$")


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
    napari_env_path: str | None = None
    thumbnail_env_path: str | None = None
    omero_instances: list[OMEROInstance] = []
    output_data_folder: str = Field(default_factory=lambda: _DEFAULT_OUTPUT_DATA_FOLDER)
    tool_store_path: str = "~/.bioimageflow/tool_packages/"
    update_mode: Literal["auto", "manual"] | str = "auto"
    execution_engine: Literal["sequential", "parsl"] = "sequential"
    cache_max_executions: int | None = Field(default=None, ge=0)
    cache_max_age: str | None = None
    keyboard_shortcuts: dict[str, str] = {}
    dev_mode: bool = True
    datasets_root: str | None = None
    max_upload_size: int = _DEFAULT_MAX_UPLOAD_SIZE

    @field_validator("cache_max_age")
    @classmethod
    def _validate_cache_max_age(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _CACHE_MAX_AGE_PATTERN.match(value):
            raise ValueError("cache_max_age must match '<int><s|m|h|d>' (e.g., '30d', '1h')")
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

    def resolved_datasets_root(self) -> str:
        """Return `datasets_root` if set, else `<output_data_folder>/datasets`."""
        if self.datasets_root:
            return self.datasets_root
        return posixpath.join(self.output_data_folder, "datasets")

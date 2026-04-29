"""Application settings models."""

from __future__ import annotations

import posixpath
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_DEFAULT_MAX_UPLOAD_SIZE = 2 * 1024**3  # 2 GB (v1 §2.4.10)
_DEFAULT_OUTPUT_DATA_FOLDER = "~/bioimageflow_data/"
_CACHE_MAX_AGE_PATTERN = re.compile(r"^\d+[smhd]$")


class OMEROInstance(BaseModel):
    """OMERO server connection configuration."""

    name: str | None = None
    host: str
    port: int = 4064
    username: str


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
            raise ValueError(
                "cache_max_age must match '<int><s|m|h|d>' (e.g., '30d', '1h')"
            )
        return value

    def resolved_datasets_root(self) -> str:
        """Return `datasets_root` if set, else `<output_data_folder>/datasets`."""
        if self.datasets_root:
            return self.datasets_root
        return posixpath.join(self.output_data_folder, "datasets")
